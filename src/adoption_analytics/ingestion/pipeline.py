"""Implémentation du pipeline d'ingestion concret pour le Learning Center.

Ce module contient la classe `LearningCenterIngestionPipeline` et le point
d'entrée CLI pour exécuter manuellement l'ingestion depuis la console.
"""

from datetime import datetime, timedelta
import argparse
import sys
from pathlib import Path
import pandas as pd
from typing import Any

from config.settings import settings
from adoption_analytics.ingestion.base import BaseIngestionPipeline
from adoption_analytics.ingestion.checkpoint import JSONCheckpointRepository, IngestionCheckpoint
from adoption_analytics.ingestion.deduplication import generate_event_id, deduplicate_events
from adoption_analytics.storage.file_repository import FileStorageRepository
from adoption_analytics.data_sources.base import normalize_usage_events, normalize_web_logs
from adoption_analytics.schemas.usage_event import validate_usage_df
from adoption_analytics.schemas.web_log import validate_web_log_df


class LearningCenterIngestionPipeline(BaseIngestionPipeline):
    """Pipeline d'ingestion incrémentale pour le service Learning Center."""

    def __init__(
        self,
        checkpoint_repo: JSONCheckpointRepository | None = None,
        storage_repo: FileStorageRepository | None = None,
        source_file_path: Path | None = None,
    ) -> None:
        super().__init__(service_name="learning_center")
        self.checkpoint_repo = checkpoint_repo or JSONCheckpointRepository()
        self.storage_repo = storage_repo or FileStorageRepository()
        
        # Résolution du fichier source nginx-events.csv
        if source_file_path:
            self.source_file_path = source_file_path
        else:
            from adoption_analytics.data_sources.learning_center.loaders import resolve_learning_center_dir
            self.source_file_path = resolve_learning_center_dir() / settings.learning_center_nginx_events_file

    def load_checkpoint(self) -> IngestionCheckpoint:
        """Charge le checkpoint.

        S'il s'agit du premier chargement (pas de checkpoint enregistré) mais que
        le stockage intermédiaire contient déjà des données historiques, initialise
        le checkpoint avec le timestamp maximum existant pour éviter de re-scanner
        l'intégralité du fichier historique.
        """
        checkpoint = self.checkpoint_repo.load(self.service_name)
        
        # Si le checkpoint est neuf (pas de timestamp précédent), on vérifie l'historique
        if checkpoint.last_processed_timestamp is None:
            existing_events = self.storage_repo.get_events(self.service_name)
            if not existing_events.empty:
                max_ts = existing_events["event_timestamp"].max()
                checkpoint.last_processed_timestamp = max_ts.isoformat()
                self.checkpoint_repo.save(checkpoint)
                
        return checkpoint

    def extract_new_data(self, checkpoint: IngestionCheckpoint) -> pd.DataFrame:
        """Lit nginx-events.csv en chunks et filtre les lignes postérieures au checkpoint."""
        if not self.source_file_path.exists():
            return pd.DataFrame()

        # Lecture par morceaux pour optimiser l'usage mémoire (fichier de 800 Mo)
        chunksize = 100_000
        new_rows = []
        last_processed = checkpoint.last_processed_timestamp
        # On lit les colonnes nécessaires pour valider, normaliser et dédupliquer
        columns = [
            "event_time_local",
            "visitor_id_approx",
            "client_ip",
            "path",
            "status",
            "user_agent",
            "analytics_eligible",
            "is_bot",
            "is_static",
            "is_api",
            "event_type",
        ]

        # Inspecte l'en-tête du fichier pour n'imposer usecols que sur les colonnes existantes
        try:
            header_df = pd.read_csv(self.source_file_path, nrows=0)
            usecols = [c for c in columns if c in header_df.columns]
        except Exception:
            return pd.DataFrame()

        # nginx-events.csv étant chronologique, on peut s'arrêter dès que les dates
        # d'un chunk sont toutes antérieures au checkpoint si on lisait à l'envers,
        # mais la lecture standard de pandas va du début à la fin.
        # Pour le POC, on scanne le fichier et on filtre les lignes supérieures au checkpoint.
        for chunk in pd.read_csv(self.source_file_path, usecols=usecols, chunksize=chunksize):
            if last_processed:
                # Comparaison de chaînes ISO (slicing) : très rapide et évite la conversion datetime
                last_proc_prefix = last_processed.replace(" ", "T")[:19]
                time_prefix = chunk["event_time_local"].astype(str).str.slice(0, 19)
                filtered_chunk = chunk[time_prefix > last_proc_prefix]
            else:
                filtered_chunk = chunk
                
            if not filtered_chunk.empty:
                new_rows.append(filtered_chunk.copy())

        if not new_rows:
            return pd.DataFrame()

        return pd.concat(new_rows, ignore_index=True)

    def validate(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Valide la présence des colonnes minimales nécessaires."""
        required = ["event_time_local", "visitor_id_approx", "client_ip", "path", "status"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            return False, [f"Colonnes brutes manquantes : {missing}"]
        return True, []

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ajoute event_timestamp normalisé et l'event_id déterministe.

        Les colonnes d'origine sont préservées pour la déduplication et les KPIs.
        """
        normalized = df.copy()
        normalized["event_timestamp"] = pd.to_datetime(normalized["event_time_local"], errors="coerce", utc=True).dt.tz_localize(None)
        normalized = normalized.dropna(subset=["event_timestamp"])
        
        # Génère les event_ids de manière vectorisée
        from adoption_analytics.ingestion.deduplication import generate_event_ids
        normalized["event_id"] = generate_event_ids(normalized)
        return normalized

    def deduplicate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Déduplique en mémoire par rapport aux IDs existants dans le repository."""
        # On charge tous les IDs existants (usage + web logs combinés pour être robuste)
        existing_ids = self.storage_repo.get_existing_event_ids(self.service_name, kind="usage")
        existing_web_ids = self.storage_repo.get_existing_event_ids(self.service_name, kind="web_logs")
        all_existing_ids = existing_ids.union(existing_web_ids)

        return deduplicate_events(df, all_existing_ids)

    def persist(self, df: pd.DataFrame) -> None:
        """Sépare les lignes dédupliquées et les persiste dans leurs fichiers respectifs."""
        # 1. Événements d'usage (uniquement analytics_eligible == 1)
        usage_raw = df[df["analytics_eligible"].fillna(0).astype(int) == 1].copy()
        if not usage_raw.empty:
            # Conversion au schéma UsageEvent canonique
            usage_normalized = normalize_usage_events(
                usage_raw.rename(columns={"visitor_id_approx": "user_id"}),
                source="learning_center_nginx",
                service="Learning Center",
            )
            # Réinjection de l'event_id
            usage_normalized["event_id"] = usage_raw["event_id"].values
            self.storage_repo.append_events(self.service_name, usage_normalized)

        # 2. Logs web complets (sécurité)
        web_raw = df.copy()
        web_normalized = normalize_web_logs(
            web_raw.rename(
                columns={
                    "client_ip": "source_ip",
                    "path": "route",
                    "status": "status_code",
                }
            ),
            source="learning_center_nginx",
        )
        web_normalized["event_id"] = web_raw["event_id"].values
        self.storage_repo.append_web_logs(self.service_name, web_normalized)

    def update_kpis(self, df: pd.DataFrame) -> None:
        """Calcule et met à jour les KPIs quotidiens de manière incrémentale.

        Pour chaque date présente dans les nouvelles données, recalcule les KPIs
        en chargeant l'historique des 30 derniers jours pour assurer la justesse
        du WAU et du MAU.
        """
        # Dates uniques présentes dans les nouvelles données
        df["date_only"] = df["event_timestamp"].dt.date
        unique_dates = sorted(df["date_only"].unique())
        
        if not unique_dates:
            return

        # Pour calculer proprement le WAU (7j) et MAU (30j), on charge l'historique
        # des 30 jours précédant la date minimale ingérée.
        min_date = min(unique_dates)
        history_start = pd.Timestamp(min_date) - timedelta(days=30)
        
        # Charge tous les logs du référentiel pour compléter les fenêtres glissantes
        all_logs = self.storage_repo.get_web_logs(self.service_name)
        
        # Fusionne historique + nouveau lot pour le calcul précis des KPIs
        if not all_logs.empty:
            all_logs["event_timestamp"] = pd.to_datetime(all_logs["event_timestamp"])
            combined_logs = pd.concat([all_logs, df], ignore_index=True).drop_duplicates(subset=["event_id"])
        else:
            combined_logs = df

        combined_logs["date_only"] = combined_logs["event_timestamp"].dt.date
        today = datetime.now().date()

        kpi_rows = []
        for d in unique_dates:
            # Fenêtres de calcul
            d_dt = pd.Timestamp(d)
            day_logs = combined_logs[combined_logs["date_only"] == d]
            
            # WAU : 7 jours glissants [d-6, d]
            wau_logs = combined_logs[
                (combined_logs["event_timestamp"] >= d_dt - timedelta(days=6)) &
                (combined_logs["event_timestamp"] <= d_dt + timedelta(hours=23, minutes=59, seconds=59))
            ]
            
            # MAU : 30 jours glissants [d-29, d]
            mau_logs = combined_logs[
                (combined_logs["event_timestamp"] >= d_dt - timedelta(days=29)) &
                (combined_logs["event_timestamp"] <= d_dt + timedelta(hours=23, minutes=59, seconds=59))
            ]

            # Filtres humains (is_bot == 0)
            day_human = day_logs[day_logs["is_bot"].fillna(0).astype(int) == 0]
            wau_human = wau_logs[wau_logs["is_bot"].fillna(0).astype(int) == 0]
            mau_human = mau_logs[mau_logs["is_bot"].fillna(0).astype(int) == 0]

            # Calculs
            dau = day_human["visitor_id_approx"].nunique()
            wau = wau_human["visitor_id_approx"].nunique()
            mau = mau_human["visitor_id_approx"].nunique()

            total_reqs = len(day_logs)
            human_reqs = len(day_human)
            
            # page_views : is_bot==0 & is_static==0 & is_api==0
            pvs = len(day_human[(day_human["is_static"].fillna(0).astype(int) == 0) & 
                                (day_human["is_api"].fillna(0).astype(int) == 0)])
            
            api_reqs = len(day_logs[day_logs["is_api"].fillna(0).astype(int) == 1])
            
            err_4xx = len(day_logs[day_logs["status"].fillna(0).astype(int).between(400, 499)])
            err_5xx = len(day_logs[day_logs["status"].fillna(0).astype(int).between(500, 599)])

            # Statut : provisoire si c'est aujourd'hui, final sinon
            status = "provisional" if d >= today else "final"

            kpi_rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "dau_approx": dau,
                "wau_approx": wau,
                "mau_approx": mau,
                "total_requests": total_reqs,
                "human_requests": human_reqs,
                "page_views": pvs,
                "api_requests": api_reqs,
                "errors_4xx": err_4xx,
                "errors_5xx": err_5xx,
                "status": status
            })

        new_kpis_df = pd.DataFrame(kpi_rows)
        self.storage_repo.upsert_daily_kpis(self.service_name, new_kpis_df)

    def save_checkpoint_on_success(self, checkpoint: IngestionCheckpoint, last_timestamp: Any, rows_added: int) -> None:
        """Enregistre le checkpoint avec succès."""
        checkpoint.last_processed_timestamp = (
            last_timestamp.isoformat() if isinstance(last_timestamp, pd.Timestamp) else str(last_timestamp)
        )
        checkpoint.last_success_timestamp = datetime.now().isoformat()
        checkpoint.rows_added = rows_added
        checkpoint.status = "SUCCESS"
        self.checkpoint_repo.save(checkpoint)

    def save_checkpoint_on_failure(self, error: Exception) -> None:
        """Enregistre l'échec dans le checkpoint sans bouger le timestamp de progression."""
        checkpoint = self.checkpoint_repo.load(self.service_name)
        checkpoint.last_success_timestamp = datetime.now().isoformat()
        checkpoint.status = "FAILED"
        self.checkpoint_repo.save(checkpoint)


# ── POINT D'ENTRÉE CLI ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline d'ingestion incrémentale AI Adoption.")
    parser.add_argument(
        "--source",
        required=True,
        choices=["learning_center"],
        help="Source de données à ingérer.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"DÉMARRAGE DE L'INGESTION INC R ÉMENTALE")
    print(f"Source traitée      : {args.source}")
    print("=" * 60)

    # Instanciation du pipeline
    checkpoint_repo = JSONCheckpointRepository()
    storage_repo = FileStorageRepository()
    
    # Récupération du checkpoint de départ pour affichage
    old_checkpoint = checkpoint_repo.load(args.source)
    print(f"Checkpoint précédent :")
    print(f"  - Dernier timestamp traité : {old_checkpoint.last_processed_timestamp}")
    print(f"  - Dernière exécution      : {old_checkpoint.last_success_timestamp}")
    print(f"  - Statut précédent        : {old_checkpoint.status}")
    print("-" * 60)

    try:
        pipeline = LearningCenterIngestionPipeline(
            checkpoint_repo=checkpoint_repo,
            storage_repo=storage_repo
        )
        
        # Exécution
        stats = pipeline.run()
        
        # Récupération du nouveau checkpoint pour affichage
        new_checkpoint = checkpoint_repo.load(args.source)
        
        print("\nINGESTION TERMINÉE AVEC SUCCÈS ✅")
        print(f"Statistiques d'exécution :")
        print(f"  - Lignes brutes lues       : {stats['rows_read']}")
        print(f"  - Doublons ignorés         : {stats['duplicates_ignored']}")
        print(f"  - Nouvelles lignes ajoutées : {stats['rows_added']}")
        print(f"  - KPIs quotidiens mis à jour: {'Oui' if stats['kpis_updated'] else 'Non'}")
        print("-" * 60)
        print(f"Nouveau Checkpoint :")
        print(f"  - Dernier timestamp traité : {new_checkpoint.last_processed_timestamp}")
        print(f"  - Exécution réussie le     : {new_checkpoint.last_success_timestamp}")
        print(f"  - Statut actuel            : {new_checkpoint.status}")
        
    except Exception as e:
        print(f"\n❌ ERREUR LORS DE L'INGESTION : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

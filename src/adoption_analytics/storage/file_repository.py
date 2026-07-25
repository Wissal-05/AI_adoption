"""Implémentation du stockage persistant basé sur des fichiers CSV.

Cette implémentation stocke les données normalisées sous forme de fichiers CSV
dans le dossier `data/processed/` de manière structurée.
Si les fichiers de stockage n'existent pas encore, ils sont initialisés
automatiquement à partir de l'historique brut disponible (fichiers originaux).
"""

import os
from pathlib import Path
import pandas as pd

from config.settings import settings
from adoption_analytics.storage.base import StorageRepository
from adoption_analytics.schemas.usage_event import empty_usage_df
from adoption_analytics.schemas.web_log import empty_web_log_df


class FileStorageRepository(StorageRepository):
    """Repository de fichiers gérant la persistance sous format CSV local.

    Sert de POC de persistance intermédiaire avant la migration SQL finale.
    Initialise automatiquement les données à partir de l'historique brut s'il est absent.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        initialize_from_raw: bool | None = None,
    ) -> None:
        """Initialise le repository de fichiers.

        Args:
            data_dir: Dossier de stockage (défaut : settings.processed_data_dir).
            initialize_from_raw: Si True, charge les fichiers bruts pour initialiser.
                                 Par défaut, désactivé si exécuté sous pytest.
        """
        self.data_dir = data_dir or settings.processed_data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if initialize_from_raw is not None:
            self.initialize_from_raw = initialize_from_raw
        else:
            import sys
            # Désactivé sous pytest par défaut
            self.initialize_from_raw = not ("pytest" in sys.modules or "unittest" in sys.modules)

    def _get_filepath(self, service_name: str, kind: str) -> Path:
        """Retourne le chemin du fichier pour un service et un type de données."""
        if kind == "usage":
            filename = f"events_{service_name}.csv"
        elif kind == "web_logs":
            filename = f"web_logs_{service_name}.csv"
        elif kind == "daily_kpis":
            filename = f"daily_kpis_{service_name}.csv"
        else:
            raise ValueError(f"Type de données inconnu : {kind}")
        return self.data_dir / filename

    def _initialize_historical_data(self, service_name: str, kind: str) -> pd.DataFrame:
        """Initialise les données à partir de l'historique brut si absent."""
        filepath = self._get_filepath(service_name, kind)
        if filepath.exists():
            return pd.read_csv(filepath)

        # Si on ne souhaite pas charger depuis le brut (ex: environnement de test)
        if not self.initialize_from_raw:
            if kind == "usage":
                return empty_usage_df()
            if kind == "web_logs":
                return empty_web_log_df()
            return pd.DataFrame()

        # Si le fichier n'existe pas, on tente de le charger à partir des sources brutes
        df = pd.DataFrame()
        if service_name == "learning_center":
            from adoption_analytics.data_sources.learning_center.loaders import (
                load_learning_center_usage_sample,
                load_learning_center_web_logs,
                load_learning_center_daily_kpis,
            )

            if kind == "usage":
                # Charge l'usage brut historique
                df = load_learning_center_usage_sample()
                if not df.empty:
                    # Rend le timestamp homogène en tz-naive UTC
                    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True).dt.tz_localize(None)
                    # Génère les event_id pour l'historique de manière vectorisée
                    from adoption_analytics.ingestion.deduplication import generate_event_ids
                    df["event_id"] = generate_event_ids(df)
            elif kind == "web_logs":
                # Charge les logs web bruts historiques
                df = load_learning_center_web_logs()
                if not df.empty:
                    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True).dt.tz_localize(None)
                    from adoption_analytics.ingestion.deduplication import generate_event_ids
                    df["event_id"] = generate_event_ids(df)
            elif kind == "daily_kpis":
                # Charge les KPIs bruts historiques
                df = load_learning_center_daily_kpis()
                if not df.empty:
                    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
                    # Par défaut, les journées historiques passées sont considérées comme finalisées (final)
                    df["status"] = "final"

        # Si on a récupéré des données historiques, on les persiste immédiatement
        if not df.empty:
            df.to_csv(filepath, index=False)
            return df

        # Sinon, retourne un DataFrame vide typé
        if kind == "usage":
            return empty_usage_df()
        if kind == "web_logs":
            return empty_web_log_df()
        return pd.DataFrame()

    def append_events(self, service_name: str, events_df: pd.DataFrame) -> None:
        """Ajoute de nouveaux événements d'usage au fichier CSV."""
        if events_df.empty:
            return

        filepath = self._get_filepath(service_name, "usage")
        existing_df = self._initialize_historical_data(service_name, "usage")

        # Fusion
        if existing_df.empty:
            combined = events_df
        else:
            # S'assurer que le format de event_id est bien en string
            existing_df["event_id"] = existing_df["event_id"].astype(str)
            events_df["event_id"] = events_df["event_id"].astype(str)
            # Éviter les doublons lors de l'écriture
            new_events = events_df[~events_df["event_id"].isin(existing_df["event_id"])]
            combined = pd.concat([existing_df, new_events], ignore_index=True)

        combined.to_csv(filepath, index=False)

    def append_web_logs(self, service_name: str, logs_df: pd.DataFrame) -> None:
        """Ajoute de nouveaux logs web bruts au fichier CSV."""
        if logs_df.empty:
            return

        filepath = self._get_filepath(service_name, "web_logs")
        existing_df = self._initialize_historical_data(service_name, "web_logs")

        if existing_df.empty:
            combined = logs_df
        else:
            existing_df["event_id"] = existing_df["event_id"].astype(str)
            logs_df["event_id"] = logs_df["event_id"].astype(str)
            new_logs = logs_df[~logs_df["event_id"].isin(existing_df["event_id"])]
            combined = pd.concat([existing_df, new_logs], ignore_index=True)

        combined.to_csv(filepath, index=False)

    def upsert_daily_kpis(self, service_name: str, kpis_df: pd.DataFrame) -> None:
        """Insère ou met à jour les indicateurs quotidiens.

        Gère l'écrasement des lignes pour les dates déjà présentes (idempotence).
        """
        if kpis_df.empty:
            return

        filepath = self._get_filepath(service_name, "daily_kpis")
        existing_df = self._initialize_historical_data(service_name, "daily_kpis")

        if existing_df.empty:
            combined = kpis_df
        else:
            # Convertit les colonnes date en chaînes YYYY-MM-DD pour la comparaison d'index
            existing_df["date"] = pd.to_datetime(existing_df["date"]).dt.strftime("%Y-%m-%d")
            kpis_df["date"] = pd.to_datetime(kpis_df["date"]).dt.strftime("%Y-%m-%d")

            # Supprime les anciennes lignes correspondant aux nouvelles dates à insérer
            existing_df = existing_df[~existing_df["date"].isin(kpis_df["date"])]
            combined = pd.concat([existing_df, kpis_df], ignore_index=True)

        # Trie par date avant de sauvegarder
        combined["date_parsed"] = pd.to_datetime(combined["date"])
        combined = combined.sort_values("date_parsed").drop(columns=["date_parsed"])
        combined.to_csv(filepath, index=False)

    def get_events(self, service_name: str) -> pd.DataFrame:
        """Charge et retourne le DataFrame complet des événements d'usage."""
        df = self._initialize_historical_data(service_name, "usage")
        if not df.empty:
            df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True).dt.tz_localize(None)
        return df

    def get_web_logs(self, service_name: str) -> pd.DataFrame:
        """Charge et retourne le DataFrame complet des logs web."""
        df = self._initialize_historical_data(service_name, "web_logs")
        if not df.empty:
            df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True).dt.tz_localize(None)
        return df

    def get_daily_kpis(self, service_name: str) -> pd.DataFrame:
        """Charge et retourne le DataFrame complet des KPIs quotidiens."""
        df = self._initialize_historical_data(service_name, "daily_kpis")
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
        return df

    def event_exists(self, service_name: str, event_id: str, kind: str = "usage") -> bool:
        """Vérifie si un événement existe déjà dans le fichier correspondant."""
        filepath = self._get_filepath(service_name, kind)
        if not filepath.exists():
            # Initialise pour vérifier si l'historique le contenait
            df = self._initialize_historical_data(service_name, kind)
        else:
            # Lecture uniquement de la colonne event_id pour optimiser
            try:
                df = pd.read_csv(filepath, usecols=["event_id"])
            except ValueError:
                # Si la colonne n'existe pas encore
                return False

        if df.empty or "event_id" not in df.columns:
            return False

        return event_id in df["event_id"].astype(str).values

    def get_existing_event_ids(self, service_name: str, kind: str = "usage") -> set[str]:
        """Retourne l'ensemble des IDs d'événements persistés dans le fichier CSV."""
        filepath = self._get_filepath(service_name, kind)
        if not filepath.exists():
            df = self._initialize_historical_data(service_name, kind)
        else:
            try:
                df = pd.read_csv(filepath, usecols=["event_id"])
            except ValueError:
                return set()

        if df.empty or "event_id" not in df.columns:
            return set()

        return set(df["event_id"].dropna().astype(str).tolist())

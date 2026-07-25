"""Contrat d'interface pour les pipelines d'ingestion incrémentale.

Définit la classe de base abstraite `BaseIngestionPipeline` qui implémente
le patron de conception Template Method pour orchestrer les étapes d'une ingestion.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Any


class BaseIngestionPipeline(ABC):
    """Classe abstraite de base pour tous les pipelines d'ingestion.

    Définit le cycle de vie de l'ingestion et délègue les implémentations
    spécifiques de lecture, validation et mise à jour aux sous-classes.
    """

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def run(self) -> dict[str, Any]:
        """Orchestre le cycle complet d'ingestion.

        Cette méthode implémente le patron Template Method. Elle exécute
        séquentiellement les étapes du pipeline et ne met à jour le checkpoint
        qu'après le succès total de toutes les étapes.

        Returns:
            Dictionnaire contenant les statistiques de l'exécution.
        """
        stats = {
            "service_name": self.service_name,
            "status": "FAILED",
            "rows_read": 0,
            "rows_rejected": 0,
            "duplicates_ignored": 0,
            "rows_added": 0,
            "kpis_updated": False,
        }

        try:
            # 1. Chargement du checkpoint précédent
            checkpoint = self.load_checkpoint()

            # 2. Extraction des données brutes
            raw_data = self.extract_new_data(checkpoint)
            stats["rows_read"] = len(raw_data)
            if raw_data.empty:
                # Aucune nouvelle donnée à traiter, fin d'exécution réussie
                stats["status"] = "SUCCESS"
                self.save_checkpoint_on_success(checkpoint, last_timestamp=checkpoint.last_processed_timestamp, rows_added=0)
                return stats

            # 3. Validation
            is_valid, warnings = self.validate(raw_data)
            if not is_valid:
                stats["rows_rejected"] = len(raw_data)
                raise ValueError(f"Échec de validation des données brutes : {warnings}")

            # 4. Normalisation
            normalized_data = self.normalize(raw_data)

            # 5. Déduplication
            deduplicated_data, dups_count = self.deduplicate(normalized_data)
            stats["duplicates_ignored"] = dups_count

            if deduplicated_data.empty:
                # Tout a été filtré comme doublon, fin d'exécution réussie
                stats["status"] = "SUCCESS"
                self.save_checkpoint_on_success(checkpoint, last_timestamp=checkpoint.last_processed_timestamp, rows_added=0)
                return stats

            # 6. Persistance des événements
            self.persist(deduplicated_data)
            stats["rows_added"] = len(deduplicated_data)

            # 7. Mise à jour des KPIs quotidiens
            self.update_kpis(deduplicated_data)
            stats["kpis_updated"] = True

            # 8. Sauvegarde du checkpoint après succès total
            # Détermine le dernier timestamp ingéré
            last_timestamp = deduplicated_data["event_timestamp"].max()
            self.save_checkpoint_on_success(checkpoint, last_timestamp, len(deduplicated_data))

            stats["status"] = "SUCCESS"

        except Exception as e:
            # En cas d'erreur, on enregistre l'échec dans le checkpoint sans avancer le timestamp
            self.save_checkpoint_on_failure(e)
            raise e

        return stats

    @abstractmethod
    def load_checkpoint(self) -> Any:
        """Charge et retourne le checkpoint précédent pour ce service."""

    @abstractmethod
    def extract_new_data(self, checkpoint: Any) -> pd.DataFrame:
        """Extrait les nouvelles données brutes apparues depuis le checkpoint."""

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Valide la structure et la qualité des données brutes extraites."""

    @abstractmethod
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convertit le DataFrame brut vers le schéma canonique de destination."""

    @abstractmethod
    def deduplicate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Déduplique les événements par rapport à l'historique et au lot en cours."""

    @abstractmethod
    def persist(self, df: pd.DataFrame) -> None:
        """Enregistre de manière persistante les nouveaux événements."""

    @abstractmethod
    def update_kpis(self, df: pd.DataFrame) -> None:
        """Calcule et met à jour les indicateurs de performance quotidiens."""

    @abstractmethod
    def save_checkpoint_on_success(self, checkpoint: Any, last_timestamp: Any, rows_added: int) -> None:
        """Valide et enregistre un checkpoint de succès."""

    @abstractmethod
    def save_checkpoint_on_failure(self, error: Exception) -> None:
        """Enregistre un checkpoint d'échec."""

"""Gestion des checkpoints pour l'ingestion incrémentale.

Définit la structure de données `IngestionCheckpoint` ainsi que le repository
d'accès abstrait et son implémentation JSON locale (POC).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from config.settings import settings


@dataclass
class IngestionCheckpoint:
    """Structure représentant le marqueur de progression d'une ingestion."""

    service_name: str
    last_processed_timestamp: str | None = None  # Format ISO ou DateString
    last_success_timestamp: str | None = None     # Date/Heure de l'exécution
    rows_added: int = 0
    status: str = "SUCCESS"  # "SUCCESS" | "FAILED"

    def to_dict(self) -> dict[str, Any]:
        """Convertit le checkpoint en dictionnaire pour sérialisation."""
        return {
            "service_name": self.service_name,
            "last_processed_timestamp": self.last_processed_timestamp,
            "last_success_timestamp": self.last_success_timestamp,
            "rows_added": self.rows_added,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IngestionCheckpoint":
        """Instancie un checkpoint depuis un dictionnaire de données."""
        return cls(
            service_name=data["service_name"],
            last_processed_timestamp=data.get("last_processed_timestamp"),
            last_success_timestamp=data.get("last_success_timestamp"),
            rows_added=data.get("rows_added", 0),
            status=data.get("status", "SUCCESS"),
        )


class CheckpointRepository(ABC):
    """Interface pour le chargement et la sauvegarde des checkpoints."""

    @abstractmethod
    def load(self, service_name: str) -> IngestionCheckpoint:
        """Charge le dernier checkpoint pour le service spécifié."""

    @abstractmethod
    def save(self, checkpoint: IngestionCheckpoint) -> None:
        """Enregistre le checkpoint."""


class JSONCheckpointRepository(CheckpointRepository):
    """Implémentation de CheckpointRepository basée sur des fichiers JSON locaux.

    Les fichiers sont stockés sous `data/processed/checkpoints/<service_name>.json`.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or (settings.processed_data_dir / "checkpoints")
        self.directory.mkdir(parents=True, exist_ok=True)

    def _get_filepath(self, service_name: str) -> Path:
        return self.directory / f"{service_name}.json"

    def load(self, service_name: str) -> IngestionCheckpoint:
        """Charge le checkpoint depuis le fichier JSON s'il existe.

        Si aucun fichier n'existe, retourne un checkpoint par défaut (initial).
        """
        filepath = self._get_filepath(service_name)
        if not filepath.exists():
            return IngestionCheckpoint(service_name=service_name)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return IngestionCheckpoint.from_dict(data)
        except Exception:
            # En cas d'erreur de lecture, retourne un checkpoint vierge
            return IngestionCheckpoint(service_name=service_name)

    def save(self, checkpoint: IngestionCheckpoint) -> None:
        """Sauvegarde le checkpoint sous format JSON."""
        filepath = self._get_filepath(checkpoint.service_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=4, ensure_ascii=False)

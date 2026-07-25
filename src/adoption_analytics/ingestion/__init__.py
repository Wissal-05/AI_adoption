"""Package d'ingestion incrémentale de la plateforme d'adoption.

Définit le contrat d'ingestion, les checkpoints, la déduplication et
les pipelines pour charger les nouvelles données de manière idempotente.
"""

from adoption_analytics.ingestion.base import BaseIngestionPipeline
from adoption_analytics.ingestion.checkpoint import IngestionCheckpoint, CheckpointRepository
from adoption_analytics.ingestion.pipeline import LearningCenterIngestionPipeline

__all__ = [
    "BaseIngestionPipeline",
    "IngestionCheckpoint",
    "CheckpointRepository",
    "LearningCenterIngestionPipeline",
]

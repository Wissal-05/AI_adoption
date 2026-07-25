"""Service d'évaluation de la fraîcheur et de la synchronisation des données.

Permet de calculer l'âge des données et le statut de synchronisation pour informer
les managers IT de retards d'ingestion ou d'indisponibilité.
"""

from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from typing import Any

from adoption_analytics.ingestion.checkpoint import JSONCheckpointRepository
from adoption_analytics.storage.file_repository import FileStorageRepository


@dataclass(frozen=True)
class FreshnessReport:
    """Structure contenant l'évaluation de la fraîcheur des données."""

    service_name: str
    min_date: str | None
    max_date: str | None
    last_success_run: str | None
    data_age_hours: float | None
    data_age_formatted: str
    status: str  # "À jour" | "En retard" | "Indisponible"


class DataFreshnessService:
    """Service d'analyse de la fraîcheur des données ingérées."""

    def __init__(
        self,
        checkpoint_repo: JSONCheckpointRepository | None = None,
        storage_repo: FileStorageRepository | None = None,
    ) -> None:
        self.checkpoint_repo = checkpoint_repo or JSONCheckpointRepository()
        self.storage_repo = storage_repo or FileStorageRepository()

    def get_freshness(self, service_name: str) -> FreshnessReport:
        """Évalue la fraîcheur des données pour un service donné.

        Détermine la plage de dates disponible, la date de dernière ingestion réussie,
        l'âge de la donnée (temps écoulé depuis le dernier événement enregistré) et
        le statut (À jour, En retard, Indisponible).
        """
        # 1. Chargement des métadonnées du checkpoint
        checkpoint = self.checkpoint_repo.load(service_name)
        last_run = checkpoint.last_success_timestamp

        # 2. Plage de dates dans le stockage
        events_df = self.storage_repo.get_events(service_name)
        if events_df.empty:
            return FreshnessReport(
                service_name=service_name,
                min_date=None,
                max_date=None,
                last_success_run=last_run,
                data_age_hours=None,
                data_age_formatted="Aucune donnée enregistrée",
                status="Indisponible",
            )

        events_df["event_timestamp"] = pd.to_datetime(events_df["event_timestamp"])
        min_ts = events_df["event_timestamp"].min()
        max_ts = events_df["event_timestamp"].max()
        
        # 3. Calcul de l'âge des données par rapport à l'heure système actuelle
        now = datetime.now()
        # Conversion du max_ts naïf/aware pour la soustraction
        if max_ts.tzinfo is not None:
            max_ts_naive = max_ts.tz_convert(None)
        else:
            max_ts_naive = max_ts

        diff = now - max_ts_naive
        age_hours = diff.total_seconds() / 3600.0

        # Formatage lisible de l'âge
        if diff.days > 0:
            age_str = f"{diff.days} jour{'s' if diff.days > 1 else ''}"
        elif age_hours >= 1.0:
            h = int(age_hours)
            age_str = f"{h} heure{'s' if h > 1 else ''}"
        else:
            m = int(diff.total_seconds() / 60)
            age_str = f"{m} minute{'s' if m > 1 else ''}"

        # 4. Détermination du statut de synchronisation
        # On considère la donnée comme "En retard" si elle a plus de 24 heures d'âge
        if age_hours > 24.0:
            status = "En retard"
        else:
            status = "À jour"

        # Si la dernière exécution a échoué
        if checkpoint.status == "FAILED":
            status = "En retard (Dernier pipeline échoué)"

        return FreshnessReport(
            service_name=service_name,
            min_date=min_ts.strftime("%Y-%m-%d %H:%M:%S"),
            max_date=max_ts.strftime("%Y-%m-%d %H:%M:%S"),
            last_success_run=last_run,
            data_age_hours=age_hours,
            data_age_formatted=age_str,
            status=status,
        )

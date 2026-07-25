import pandas as pd

from adoption_analytics.metrics.adoption import (
    compute_adoption_metrics,
    compute_usage_rate,
)


class AdoptionMetricsService:
    """Service central pour calculer les KPI d'adoption."""

    @staticmethod
    def compute(
        usage_events: pd.DataFrame,
        reference_date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        return compute_adoption_metrics(
            usage_events,
            reference_date=reference_date,
        )

    @staticmethod
    def usage_rate(
        active_users: int,
        eligible_users: int,
    ) -> float | None:
        return compute_usage_rate(
            active_users=active_users,
            eligible_users=eligible_users,
        )
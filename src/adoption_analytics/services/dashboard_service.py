"""Service de tableau de bord — orchestration principale.

DashboardService coordonne le chargement des données, le calcul des métriques
et la construction des ViewModels consommés par l'UI.

L'UI appelle uniquement ce service. Elle ne doit jamais importer directement
les métriques, les connecteurs ou le registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from adoption_analytics.data_sources.registry import DashboardData, load_dashboard_data
from adoption_analytics.metrics.adoption import (
    adoption_timeseries,
    departmental_breakdown,
    find_underused_services,
    inactive_users,
)
from adoption_analytics.services.adoption_metrics_service import AdoptionMetricsService
from adoption_analytics.metrics.learning_center import (
    latest_daily_kpis,
    prepare_daily_trend,
    route_type_summary,
)
from adoption_analytics.reporting.alerts import build_usage_drop_alerts
from adoption_analytics.reporting.weekly import build_weekly_summary


@dataclass
class AdoptionViewModel:
    """ViewModel agrégé pour l'onglet Adoption de l'UI."""

    metrics: dict[str, float]
    timeseries: pd.DataFrame
    departmental: pd.DataFrame
    underused: pd.DataFrame
    inactive: pd.DataFrame
    weekly_summary: str
    alerts: list[str]


@dataclass
class LearningCenterViewModel:
    """ViewModel agrégé pour l'onglet Learning Center de l'UI."""

    latest_kpis: dict[str, int | float | str]
    daily_trend: pd.DataFrame
    daily_kpis: pd.DataFrame
    top_routes: pd.DataFrame
    route_summary: pd.DataFrame
    source_dir: str


class DashboardService:
    """Orchestre le chargement et le calcul des données du tableau de bord.

    Usage dans app.py :
        service = DashboardService()
        data = service.load()
        adoption_vm = service.get_adoption_view(filtered_usage_df)
        lc_vm = service.get_learning_center_view()
    """

    def __init__(self) -> None:
        self._data: DashboardData | None = None

    def load(self) -> DashboardData:
        """Charge toutes les sources et met en cache le DashboardData."""
        self._data = load_dashboard_data()
        return self._data

    @property
    def data(self) -> DashboardData:
        if self._data is None:
            raise RuntimeError("Appelez load() avant d'accéder aux données.")
        return self._data

    def get_adoption_view(self, filtered_usage: pd.DataFrame) -> AdoptionViewModel:
        """Calcule toutes les métriques d'adoption pour un DataFrame filtré."""
        return AdoptionViewModel(
            metrics=AdoptionMetricsService.compute(filtered_usage),
            timeseries=adoption_timeseries(filtered_usage),
            departmental=departmental_breakdown(filtered_usage),
            underused=find_underused_services(filtered_usage),
            inactive=inactive_users(self.data.usage_events),
            weekly_summary=build_weekly_summary(filtered_usage),
            alerts=build_usage_drop_alerts(filtered_usage),
        )

    def get_learning_center_view(self) -> LearningCenterViewModel:
        """Agrège les données source-spécifiques Learning Center pour l'UI."""
        daily_kpis = self.data.learning_center_daily
        top_routes = self.data.learning_center_top_routes

        learning_center_events = self.data.usage_events[
            self.data.usage_events["service"] == "Learning Center"
        ]

        adoption_metrics = AdoptionMetricsService.compute(learning_center_events)

        raw_kpis = latest_daily_kpis(daily_kpis)

        for key in ("dau_approx", "wau_approx", "mau_approx"):
            raw_kpis.pop(key, None)

        latest_kpis = {
            **raw_kpis,
            "dau": adoption_metrics["dau"],
            "wau": adoption_metrics["wau"],
            "mau": adoption_metrics["mau"],
        }

        return LearningCenterViewModel(
            latest_kpis=latest_kpis,
            daily_trend=prepare_daily_trend(daily_kpis),
            daily_kpis=daily_kpis,
            top_routes=top_routes,
            route_summary=route_type_summary(top_routes),
            source_dir=self.data.learning_center_source_dir,
        )
    
    def get_available_sources(self) -> list[str]:
        """Retourne la liste des sources de données effectivement chargées."""
        return self.data.available_sources

    def get_filter_options(self, usage_df: pd.DataFrame) -> dict[str, list[str]]:
        """Calcule les options de filtre (services, départements) pour la sidebar."""
        if usage_df.empty:
            return {"services": [], "departments": []}
        return {
            "services": sorted(usage_df["service"].dropna().unique().tolist()),
            "departments": sorted(usage_df["department"].dropna().unique().tolist()),
        }

    @staticmethod
    def apply_filters(
        usage_df: pd.DataFrame,
        services: list[str],
        departments: list[str],
    ) -> pd.DataFrame:
        """Filtre le DataFrame usage selon les services et départements sélectionnés."""
        if usage_df.empty:
            return usage_df
        return usage_df[
            usage_df["service"].isin(services) & usage_df["department"].isin(departments)
        ].copy()

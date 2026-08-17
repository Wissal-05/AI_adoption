"""Service de tableau de bord — orchestration principale.

DashboardService coordonne le chargement des données, le calcul des métriques
et la construction des ViewModels consommés par l'UI.

L'UI appelle uniquement ce service. Elle ne doit jamais importer directement
les métriques, les connecteurs ou le registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
class ServiceExtendedAnalytics:
    """Modèle générique pour les analytics enrichies par service."""
    status: str
    usage: dict[str, Any] | None = None
    connection: dict[str, Any] | None = None
    adoption_by_module: list[dict[str, Any]] | None = None
    adoption_by_campus: list[dict[str, Any]] | None = None
    data_quality: dict[str, Any] | None = None


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

    def get_adoption_view(self, filtered_usage: pd.DataFrame, reference_date: pd.Timestamp | None = None, kpi_usage: pd.DataFrame | None = None) -> AdoptionViewModel:
        """Calcule toutes les métriques d'adoption pour un DataFrame filtré."""
        if kpi_usage is None:
            kpi_usage = filtered_usage
        return AdoptionViewModel(
            metrics=AdoptionMetricsService.compute(kpi_usage, reference_date=reference_date),
            timeseries=adoption_timeseries(filtered_usage),
            departmental=departmental_breakdown(filtered_usage),
            underused=find_underused_services(filtered_usage),
            inactive=inactive_users(self.data.usage_events),
            weekly_summary=build_weekly_summary(filtered_usage),
            alerts=build_usage_drop_alerts(filtered_usage),
        )

    def get_global_overview(self, filtered_usage: pd.DataFrame, available_services: list[str], reference_date: pd.Timestamp | None = None, kpi_usage: pd.DataFrame | None = None) -> dict:
        """Calcule les synthèses globales pour 'Tous les services'."""
        if kpi_usage is None:
            kpi_usage = filtered_usage
        services_suivis = len(available_services)
        services_avec_donnees = filtered_usage["service"].nunique() if not filtered_usage.empty else 0
        volume_observe = len(filtered_usage)

        fraicheur = "N/A"
        if not filtered_usage.empty:
            max_dates = filtered_usage.groupby("service")["event_timestamp"].max()
            if max_dates.nunique() > 1:
                fraicheur = "Hétérogène"
            else:
                max_d = max_dates.max()
                fraicheur = max_d.strftime("%d/%m/%Y") if pd.notnull(max_d) else "N/A"
        
        table_data = []
        for srv in available_services:
            srv_df = filtered_usage[filtered_usage["service"] == srv].copy()
            srv_kpi_df = kpi_usage[kpi_usage["service"] == srv].copy()
            if not srv_df.empty:
                max_date = srv_df["event_timestamp"].max()
                
                if srv.lower() == "booking":
                    extended = self.get_service_extended_analytics(srv, reference_date=reference_date)
                    if extended and extended.usage:
                        dau = extended.usage.get("dau", 0) or 0
                        wau = extended.usage.get("wau", 0) or 0
                        mau = extended.usage.get("mau", 0) or 0
                    else:
                        dau = wau = mau = 0
                else:
                    metrics = AdoptionMetricsService.compute(srv_kpi_df, reference_date=reference_date)
                    dau = metrics.get("dau", 0) or 0
                    wau = metrics.get("wau", 0) or 0
                    mau = metrics.get("mau", 0) or 0

                table_data.append({
                    "Service": srv,
                    "DAU": int(dau),
                    "WAU": int(wau),
                    "MAU": int(mau),
                    "Dernière donnée disponible": max_date.strftime("%d/%m/%Y") if pd.notnull(max_date) else "N/A"
                })
                
        return {
            "services_suivis": services_suivis,
            "services_avec_donnees": services_avec_donnees,
            "volume_observe": volume_observe,
            "fraicheur": fraicheur,
            "table_data": table_data
        }

    def get_service_extended_analytics(self, service_name: str, reference_date: pd.Timestamp | None = None, window_days: int = 30) -> ServiceExtendedAnalytics:
        """Expose les analytics enrichies pour un service donné."""
        if service_name == "Booking":
            raw = self.data.raw_by_source.get("booking", {})
            events = raw.get("events", pd.DataFrame())
            sessions = raw.get("sessions", pd.DataFrame())
            users = raw.get("users", pd.DataFrame())
            eligible = raw.get("eligible", pd.DataFrame())
            
            if events.empty and sessions.empty:
                return ServiceExtendedAnalytics(status="not_available")
                
            from adoption_analytics.metrics.booking_metrics import (
                compute_booking_usage_kpis,
                compute_booking_connection_kpis,
                compute_booking_adoption_by_module,
                compute_booking_adoption_by_campus,
                compute_booking_data_quality
            )
            
            return ServiceExtendedAnalytics(
                status="available",
                usage=compute_booking_usage_kpis(events, reference_date=reference_date),
                connection=compute_booking_connection_kpis(sessions, events, reference_date=reference_date, window_days=window_days),
                adoption_by_module=compute_booking_adoption_by_module(events, eligible, reference_date=reference_date, window_days=window_days),
                adoption_by_campus=compute_booking_adoption_by_campus(events, eligible, users, reference_date=reference_date, window_days=window_days),
                data_quality=compute_booking_data_quality(events, sessions, users)
            )
            
        return ServiceExtendedAnalytics(status="not_available")

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
    
    def get_trend_warning_message(self, filtered_usage: pd.DataFrame, selected_service: str) -> str | None:
        """Détermine le message d'avertissement d'historique pour les graphiques de tendance."""
        if selected_service == "Tous les services":
            if not filtered_usage.empty and "event_timestamp" in filtered_usage.columns:
                max_dates = filtered_usage.groupby("service")["event_timestamp"].max().dt.normalize()
                min_dates = filtered_usage.groupby("service")["event_timestamp"].min().dt.normalize()
                if max_dates.nunique() > 1 or min_dates.nunique() > 1:
                    return (
                        "Les périodes disponibles diffèrent selon les services. "
                        "Consultez la dernière date disponible de chaque service "
                        "pour interpréter les tendances."
                    )
        else:
            if not filtered_usage.empty and "event_timestamp" in filtered_usage.columns:
                unique_days = pd.to_datetime(filtered_usage["event_timestamp"], errors="coerce").dt.normalize().nunique()
                if unique_days == 1:
                    return (
                        "Historique insuffisant pour analyser une tendance. "
                        "Une seule journée de données est actuellement disponible."
                    )
        return None

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

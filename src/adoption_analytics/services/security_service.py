"""Service de sécurité — détection et agrégation des événements suspects.

SecurityService coordonne la lecture des logs web bruts (produits par les
connecteurs) et l'application des règles de détection sécurité (métriques).

Ce service résout le couplage data_sources ↔ metrics qui existait avant la
refactorisation : le connecteur produit maintenant des logs bruts normalisés,
et c'est ce service qui y applique la détection sécurité.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from adoption_analytics.metrics.security import detect_suspicious_routes, summarize_security_events
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS, empty_web_log_df


@dataclass
class SecurityViewModel:
    """ViewModel agrégé pour l'onglet Security Analytics de l'UI."""

    suspicious_events: pd.DataFrame
    """Événements suspects filtrés (avec colonnes is_error et risk_label)."""

    summary: dict[str, int]
    """Résumé statistique : unique_ips, unique_routes, error_events."""

    top_routes: pd.DataFrame
    """Top 20 routes suspectes par nombre de requêtes."""

    top_ips: pd.DataFrame
    """Top 20 IP sources par nombre de requêtes suspectes."""

    total_suspicious: int
    """Nombre total d'événements suspects."""


class SecurityService:
    """Orchestre la détection sécurité à partir des logs web bruts.

    Usage dans app.py :
        from adoption_analytics.services.security_service import SecurityService
        security_vm = SecurityService.analyze(web_logs_df)
    """

    @staticmethod
    def analyze(
        web_logs_df: pd.DataFrame,
        suspicious_patterns: list[str] | None = None,
    ) -> SecurityViewModel:
        """Analyse les logs web bruts et retourne un SecurityViewModel.

        Args:
            web_logs_df: DataFrame conforme au schéma WebLog (produit par les connecteurs).
            suspicious_patterns: patterns de routes suspects (défaut: depuis settings).

        Returns:
            SecurityViewModel prêt à l'affichage.
        """
        if web_logs_df.empty:
            return SecurityViewModel(
                suspicious_events=empty_web_log_df(),
                summary={"unique_ips": 0, "unique_routes": 0, "error_events": 0},
                top_routes=pd.DataFrame(columns=["route", "requests"]),
                top_ips=pd.DataFrame(columns=["source_ip", "requests"]),
                total_suspicious=0,
            )

        suspicious = detect_suspicious_routes(web_logs_df, suspicious_patterns)
        summary = summarize_security_events(suspicious)

        top_routes = pd.DataFrame(columns=["route", "requests"])
        top_ips = pd.DataFrame(columns=["source_ip", "requests"])

        if not suspicious.empty:
            route_counts = suspicious["route"].value_counts().head(20).reset_index()
            route_counts.columns = ["route", "requests"]
            top_routes = route_counts

            ip_counts = suspicious["source_ip"].value_counts().head(20).reset_index()
            ip_counts.columns = ["source_ip", "requests"]
            top_ips = ip_counts

        return SecurityViewModel(
            suspicious_events=suspicious,
            summary=summary,
            top_routes=top_routes,
            top_ips=top_ips,
            total_suspicious=len(suspicious),
        )

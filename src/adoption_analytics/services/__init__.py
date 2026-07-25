"""Couche services — orchestration applicative.

Les services coordonnent les sources de données et les métriques pour
fournir à l'UI des objets prêts à l'affichage (ViewModels).

L'UI (app.py) ne doit appeler que les services, jamais les métriques
ou les connecteurs directement.
"""

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.services.security_service import SecurityService
from adoption_analytics.services.data_freshness import DataFreshnessService

__all__ = ["DashboardService", "SecurityService", "DataFreshnessService"]

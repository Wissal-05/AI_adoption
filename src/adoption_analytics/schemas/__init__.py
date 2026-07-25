"""Schémas canoniques partagés entre toutes les couches de l'application."""

from adoption_analytics.schemas.usage_event import USAGE_COLUMNS, UsageEventSchema
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS, WebLogSchema

__all__ = [
    "USAGE_COLUMNS",
    "WEB_LOG_COLUMNS",
    "UsageEventSchema",
    "WebLogSchema",
]

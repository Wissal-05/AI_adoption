"""Base abstraite des connecteurs de données.

Toutes les sources de données héritent de DataSource et produisent
exclusivement des DataFrames conformes aux schémas canoniques définis
dans adoption_analytics.schemas.

Règle architecturale :
  Ce module ne doit jamais importer de adoption_analytics.metrics.
  La séparation infra (données) / domaine (métriques) est stricte.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from adoption_analytics.schemas.usage_event import USAGE_COLUMNS, empty_usage_df
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS, empty_web_log_df


@dataclass(frozen=True)
class DataSourceConfig:
    """Configuration d'une source de données."""

    name: str
    path: Path
    kind: str  # "usage" | "web_logs"


class DataSource(ABC):
    """Interface abstraite de tous les connecteurs de données."""

    def __init__(self, config: DataSourceConfig) -> None:
        self.config = config

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Charge, normalise et retourne un DataFrame conforme au schéma canonique."""


def read_csv_if_exists(path: Path, **kwargs) -> pd.DataFrame:
    """Lit un CSV si le fichier existe, retourne un DataFrame vide sinon."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def normalize_usage_events(df: pd.DataFrame, source: str, service: str | None = None) -> pd.DataFrame:
    """Normalise un DataFrame brut vers le schéma canonique UsageEvent.

    Applique les renommages standards de colonnes, complète les colonnes
    manquantes avec des valeurs par défaut, et filtre les lignes invalides.
    """
    if df.empty:
        return empty_usage_df()

    normalized = df.copy()
    rename_map = {
        "timestamp": "event_timestamp",
        "datetime": "event_timestamp",
        "date": "event_timestamp",
        "user": "user_id",
        "dept": "department",
        "app": "service",
        "event": "action",
    }
    normalized = normalized.rename(columns={k: v for k, v in rename_map.items() if k in normalized.columns})

    if "service" not in normalized.columns:
        normalized["service"] = service or source
    if "source" not in normalized.columns:
        normalized["source"] = source
    if "action" not in normalized.columns:
        normalized["action"] = "visit"
    if "department" not in normalized.columns:
        normalized["department"] = "Unknown"

    normalized["event_timestamp"] = pd.to_datetime(normalized["event_timestamp"], errors="coerce")
    normalized = normalized.dropna(subset=["event_timestamp", "user_id"])
    return normalized.reindex(columns=USAGE_COLUMNS)


def normalize_web_logs(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Normalise un DataFrame brut vers le schéma canonique WebLog.

    Applique les renommages standards de colonnes, complète les colonnes
    manquantes avec des valeurs par défaut, et filtre les lignes invalides.
    """
    if df.empty:
        return empty_web_log_df()

    normalized = df.copy()
    rename_map = {
        "timestamp": "event_timestamp",
        "datetime": "event_timestamp",
        "ip": "source_ip",
        "client_ip": "source_ip",
        "path": "route",
        "url_path": "route",
        "status": "status_code",
        "http_status": "status_code",
        "agent": "user_agent",
    }
    normalized = normalized.rename(columns={k: v for k, v in rename_map.items() if k in normalized.columns})

    if "source" not in normalized.columns:
        normalized["source"] = source
    if "user_agent" not in normalized.columns:
        normalized["user_agent"] = ""

    normalized["event_timestamp"] = pd.to_datetime(normalized["event_timestamp"], errors="coerce")
    normalized["status_code"] = pd.to_numeric(normalized["status_code"], errors="coerce").fillna(0).astype(int)
    normalized = normalized.dropna(subset=["event_timestamp", "source_ip", "route"])
    return normalized.reindex(columns=WEB_LOG_COLUMNS)

"""Fonctions de chargement spécialisées pour le Learning Center.

Ce module gère la résolution du dossier source (dépôt vs externe), la lecture
des trois fichiers CSV Learning Center et leur normalisation vers les schémas
canoniques. Il NE contient PAS de logique de détection sécurité.

Règle architecturale :
  Ce module ne doit jamais importer de adoption_analytics.metrics.
  Le filtrage sécurité est délégué à services.security_service.
"""

from pathlib import Path

import pandas as pd

from config.settings import settings
from adoption_analytics.data_sources.base import (
    normalize_web_logs,
    read_csv_if_exists,
)
from adoption_analytics.schemas.usage_event import USAGE_COLUMNS, empty_usage_df
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS, empty_web_log_df


def resolve_learning_center_dir() -> Path:
    """Résout le dossier Learning Center actif.

    Priorité :
      1. Dossier dans le dépôt (learning_center_repo_dir) si daily-kpis.csv présent.
      2. Dossier externe configuré (learning_center_data_dir).
    """
    repo_path = settings.learning_center_repo_dir / settings.learning_center_daily_kpis_file
    if repo_path.exists():
        return settings.learning_center_repo_dir
    return settings.learning_center_data_dir


def load_learning_center_daily_kpis() -> pd.DataFrame:
    """Charge et normalise le fichier daily-kpis.csv Learning Center."""
    path = resolve_learning_center_dir() / settings.learning_center_daily_kpis_file
    df = read_csv_if_exists(path)
    if df.empty:
        return _empty_daily_kpis()

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    df["service"] = "Learning Center"
    return df


def load_learning_center_top_routes() -> pd.DataFrame:
    """Charge et trie le fichier top-routes.csv Learning Center."""
    path = resolve_learning_center_dir() / settings.learning_center_top_routes_file
    df = read_csv_if_exists(path)
    if df.empty:
        return pd.DataFrame(columns=["path", "requests"])

    df = df.copy()
    df["requests"] = pd.to_numeric(df["requests"], errors="coerce").fillna(0).astype(int)
    return df.sort_values("requests", ascending=False)


def load_learning_center_usage_sample(
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Charge un échantillon d'événements d'usage depuis nginx-events.csv.

    Filtre uniquement les lignes analytics_eligible == 1 et normalise
    vers le schéma UsageEvent canonique.
    """
    actual_max_rows = max_rows if max_rows is not None else settings.lc_event_sample_rows
    path = resolve_learning_center_dir() / settings.learning_center_nginx_events_file
    if not path.exists():
        return empty_usage_df()

    columns = [
        "event_time_local",
        "visitor_id_approx",
        "event_type",
        "path",
        "analytics_eligible",
    ]
    raw = pd.read_csv(path, usecols=columns, nrows=actual_max_rows)
    raw = raw[raw["analytics_eligible"].fillna(0).astype(int) == 1].copy()
    if raw.empty:
        return empty_usage_df()

    normalized = pd.DataFrame(
        {
            "event_timestamp": pd.to_datetime(raw["event_time_local"], errors="coerce"),
            "user_id": raw["visitor_id_approx"].astype(str),
            "department": "Unknown",
            "service": "Learning Center",
            "action": raw["event_type"].fillna("visit"),
            "source": "learning_center_nginx",
        }
    )
    return normalized.dropna(subset=["event_timestamp", "user_id"]).reindex(columns=USAGE_COLUMNS)


def load_learning_center_web_logs(
    max_rows: int | None = None,
    chunksize: int = 50_000,
) -> pd.DataFrame:
    """Charge les logs web bruts depuis nginx-events.csv (schéma WebLog canonique).

    Retourne TOUS les logs normalisés, sans filtrage sécurité.
    Le filtrage est délégué à services.security_service.

    Args:
        max_rows: nombre maximum de lignes à scanner (défaut: settings.lc_security_scan_max_rows).
        chunksize: taille des chunks de lecture pour les gros fichiers.
    """
    actual_max_rows = max_rows if max_rows is not None else settings.lc_security_scan_max_rows
    path = resolve_learning_center_dir() / settings.learning_center_nginx_events_file
    if not path.exists():
        return empty_web_log_df()

    columns = ["event_time_local", "client_ip", "remote_addr", "path", "status", "user_agent"]
    chunks: list[pd.DataFrame] = []
    scanned_rows = 0

    for chunk in pd.read_csv(path, usecols=columns, chunksize=chunksize):
        scanned_rows += len(chunk)
        normalized = normalize_web_logs(
            chunk.rename(
                columns={
                    "event_time_local": "event_timestamp",
                    "client_ip": "source_ip",
                    "path": "route",
                    "status": "status_code",
                }
            ),
            source="learning_center_nginx",
        )
        if not normalized.empty:
            chunks.append(normalized)
        if scanned_rows >= actual_max_rows:
            break

    if not chunks:
        return empty_web_log_df()

    return pd.concat(chunks, ignore_index=True).sort_values("event_timestamp", ascending=False)


# Alias de compatibilité ascendante — conservé le temps que les anciens imports soient migrés.
# TODO: supprimer après migration complète du registry et des services.
def load_learning_center_security_events(
    max_rows: int | None = None,
    chunksize: int = 50_000,
) -> pd.DataFrame:
    """Alias vers load_learning_center_web_logs + filtrage sécurité.

    Conservé pour la compatibilité ascendante avec l'ancien registry.
    Préférer services.security_service.get_security_summary() dans le nouveau code.
    """
    from adoption_analytics.metrics.security import detect_suspicious_routes  # import local intentionnel

    web_logs = load_learning_center_web_logs(max_rows=max_rows, chunksize=chunksize)
    if web_logs.empty:
        return pd.DataFrame(columns=WEB_LOG_COLUMNS + ["is_error", "risk_label"])
    return detect_suspicious_routes(web_logs)


def _empty_daily_kpis() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "dau_approx",
            "wau_approx",
            "mau_approx",
            "total_requests",
            "human_requests",
            "page_views",
            "api_requests",
            "errors_4xx",
            "errors_5xx",
            "service",
        ]
    )

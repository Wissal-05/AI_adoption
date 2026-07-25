"""Schéma canonique des logs web / sécurité.

Toutes les sources de logs web (nginx Learning Center, futures applications)
doivent produire un DataFrame conforme à ce schéma avant d'être transmises
aux couches métriques et reporting.
"""

from typing import TypedDict

import pandas as pd

WEB_LOG_COLUMNS: list[str] = [
    "event_timestamp",  # datetime64[ns] — date/heure de la requête
    "source_ip",        # str — adresse IP source
    "route",            # str — route demandée (ex: "/wp-admin")
    "status_code",      # int — code HTTP (ex: 404, 200)
    "user_agent",       # str — user-agent si disponible
    "source",           # str — application source (ex: "learning_center_nginx")
]


class WebLogSchema(TypedDict):
    """Typage structurel d'une ligne de log web."""

    event_timestamp: pd.Timestamp
    source_ip: str
    route: str
    status_code: int
    user_agent: str
    source: str


def empty_web_log_df() -> pd.DataFrame:
    """Retourne un DataFrame vide conforme au schéma web log."""
    return pd.DataFrame(columns=WEB_LOG_COLUMNS)


def validate_web_log_df(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Valide qu'un DataFrame est conforme au schéma web log.

    Returns:
        (is_valid, list_of_warnings): tuple indiquant la validité et les
        avertissements détectés.
    """
    warnings: list[str] = []

    missing = [col for col in WEB_LOG_COLUMNS if col not in df.columns]
    if missing:
        warnings.append(f"Colonnes manquantes: {missing}")
        return False, warnings

    if not pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
        warnings.append("event_timestamp n'est pas de type datetime64.")

    null_critical = df[["event_timestamp", "source_ip", "route"]].isnull().any()
    for col, has_null in null_critical.items():
        if has_null:
            warnings.append(f"Valeurs nulles détectées dans la colonne critique '{col}'.")

    return len(warnings) == 0, warnings

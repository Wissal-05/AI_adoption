"""Schéma canonique des événements d'usage.

Toutes les sources de données (Learning Center, Booking, futures applications)
doivent produire un DataFrame conforme à ce schéma avant d'être transmises
aux couches métriques et reporting.
"""

from typing import TypedDict

import pandas as pd

USAGE_COLUMNS: list[str] = [
    "event_timestamp",  # datetime64[ns] — date/heure de l'événement
    "user_id",          # str — identifiant anonymisé de l'utilisateur
    "department",       # str — département/service de l'utilisateur
    "service",          # str — application utilisée (ex: "Learning Center")
    "action",           # str — action fonctionnelle (ex: "login", "visit")
    "source",           # str — source technique du log (ex: "learning_center_nginx")
    # --- Booking spécifiques ---
    "module",           # str — module Booking (ex: HOUSING)
    "business_status",  # str — statut métier de l'action
    "user_role",        # str — rôle de l'utilisateur
    "user_status",      # str — statut de l'utilisateur
    "campus_name",      # str — campus
    "entity_name",      # str — entité
]


class UsageEventSchema(TypedDict):
    """Typage structurel d'une ligne d'événement d'usage."""

    event_timestamp: pd.Timestamp
    user_id: str
    department: str
    service: str
    action: str
    source: str
    module: str
    business_status: str
    user_role: str
    user_status: str
    campus_name: str
    entity_name: str


def empty_usage_df() -> pd.DataFrame:
    """Retourne un DataFrame vide conforme au schéma usage."""
    return pd.DataFrame(columns=USAGE_COLUMNS)


def validate_usage_df(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Valide qu'un DataFrame est conforme au schéma usage.

    Returns:
        (is_valid, list_of_warnings): tuple indiquant la validité et les
        avertissements détectés (colonnes manquantes, types incorrects, etc.)
    """
    warnings: list[str] = []

    missing = [col for col in USAGE_COLUMNS if col not in df.columns]
    if missing:
        warnings.append(f"Colonnes manquantes: {missing}")
        return False, warnings

    if not pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
        warnings.append("event_timestamp n'est pas de type datetime64.")

    null_critical = df[["event_timestamp", "user_id"]].isnull().any()
    for col, has_null in null_critical.items():
        if has_null:
            warnings.append(f"Valeurs nulles détectées dans la colonne critique '{col}'.")

    return len(warnings) == 0, warnings

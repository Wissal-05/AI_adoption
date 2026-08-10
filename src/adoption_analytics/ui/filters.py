from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class DateWindow:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    label: str


PERIOD_OPTIONS = [
    "Toute la période disponible",
    "Aujourdhui",
    "Hier",
    "7 derniers jours",
    "30 derniers jours",
    "60 derniers jours",
    "Cette semaine",
    "Ce mois",
    "Période personnalisée",
]


def _normalize_date(value) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def get_available_date_bounds(
    df: pd.DataFrame,
    timestamp_column: str = "event_timestamp",
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if df is None or df.empty or timestamp_column not in df.columns:
        return None, None

    timestamps = pd.to_datetime(df[timestamp_column], errors="coerce").dropna()

    if timestamps.empty:
        return None, None

    return timestamps.min().normalize(), timestamps.max().normalize()


def resolve_period(
    period_label: str,
    available_start: pd.Timestamp,
    available_end: pd.Timestamp,
    custom_start: date | pd.Timestamp | None = None,
    custom_end: date | pd.Timestamp | None = None,
) -> DateWindow:
    if available_start is None or available_end is None:
        raise ValueError("Aucune période disponible.")

    available_start = _normalize_date(available_start)
    available_end = _normalize_date(available_end)

    reference_date = available_end

    if period_label == "Toute la période disponible":
        start = available_start
        end = available_end

    elif period_label == "Aujourdhui":
        start = reference_date
        end = reference_date

    elif period_label == "Hier":
        start = reference_date - pd.Timedelta(days=1)
        end = start

    elif period_label == "7 derniers jours":
        end = reference_date
        start = end - pd.Timedelta(days=6)

    elif period_label == "30 derniers jours":
        end = reference_date
        start = end - pd.Timedelta(days=29)

    elif period_label == "60 derniers jours":
        end = reference_date
        start = end - pd.Timedelta(days=59)

    elif period_label == "Cette semaine":
        end = reference_date
        start = end - pd.Timedelta(days=end.weekday())

    elif period_label == "Ce mois":
        end = reference_date
        start = reference_date.replace(day=1)

    elif period_label == "Période personnalisée":
        if custom_start is None or custom_end is None:
            raise ValueError("Les dates personnalisées sont obligatoires.")

        start = _normalize_date(custom_start)
        end = _normalize_date(custom_end)

        if start > end:
            raise ValueError("La date de début doit précéder la date de fin.")

    else:
        raise ValueError(f"Période inconnue : {period_label}")

    # Ne jamais demander une période en dehors des données connues.
    start = max(start, available_start)
    end = min(end, available_end)

    return DateWindow(
        start_date=start,
        end_date=end,
        label=period_label,
    )


def apply_date_filter(
    df: pd.DataFrame,
    window: DateWindow,
    timestamp_column: str = "event_timestamp",
) -> pd.DataFrame:
    if df is None or df.empty or timestamp_column not in df.columns:
        return df.copy()

    result = df.copy()

    timestamps = pd.to_datetime(
        result[timestamp_column],
        errors="coerce",
    )

    mask = (
        timestamps.dt.normalize().ge(window.start_date)
        & timestamps.dt.normalize().le(window.end_date)
    )

    return result.loc[mask].copy()


def get_previous_window(window: DateWindow) -> DateWindow:
    duration_days = (window.end_date - window.start_date).days + 1

    previous_end = window.start_date - pd.Timedelta(days=1)
    previous_start = previous_end - pd.Timedelta(days=duration_days - 1)

    return DateWindow(
        start_date=previous_start,
        end_date=previous_end,
        label="Période précédente",
    )


def compute_period_change(
    current_value: float | int | None,
    previous_value: float | int | None,
) -> float | None:
    if current_value is None or previous_value is None:
        return None

    try:
        current = float(current_value)
        previous = float(previous_value)
    except (TypeError, ValueError):
        return None

    if previous == 0:
        return None

    return ((current - previous) / previous) * 100

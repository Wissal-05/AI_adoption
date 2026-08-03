from datetime import timedelta

import pandas as pd

from config.settings import settings


def _with_date(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["event_timestamp"] = pd.to_datetime(data["event_timestamp"], errors="coerce")
    data["date"] = data["event_timestamp"].dt.date
    return data.dropna(subset=["event_timestamp"])


def compute_adoption_metrics(df: pd.DataFrame, reference_date: pd.Timestamp | None = None) -> dict[str, float]:
    if df.empty:
        return {"dau": 0, "wau": 0, "mau": 0, "avg_events_per_active_user": 0.0}

    data = _with_date(df)
    current_date = (reference_date or data["event_timestamp"].max()).normalize()
    day_start = current_date
    week_start = current_date - timedelta(days=6)
    month_start = current_date - timedelta(days=29)

    active_users = data["user_id"].nunique()
    return {
        "dau": data[data["event_timestamp"] >= day_start]["user_id"].nunique(),
        "wau": data[data["event_timestamp"] >= week_start]["user_id"].nunique(),
        "mau": data[data["event_timestamp"] >= month_start]["user_id"].nunique(),
        "avg_events_per_active_user": len(data) / active_users if active_users else 0.0,
    }


def adoption_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "service", "active_users", "events"])

    data = _with_date(df)
    return (
        data.groupby(["date", "service"], as_index=False)
        .agg(active_users=("user_id", "nunique"), events=("user_id", "size"))
        .sort_values(["date", "service"])
    )


def departmental_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "department",
                "service",
                "active_users",
                "events",
                "avg_events_per_user",
                "share_of_active_users",
            ]
        )

    required_columns = {"department", "service", "user_id"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        return pd.DataFrame(
            columns=[
                "department",
                "service",
                "active_users",
                "events",
                "avg_events_per_user",
                "share_of_active_users",
            ]
        )

    grouped = (
        df.groupby(["department", "service"], as_index=False)
        .agg(
            active_users=("user_id", "nunique"),
            events=("user_id", "size"),
        )
    )

    grouped["avg_events_per_user"] = (
        grouped["events"] / grouped["active_users"].clip(lower=1)
    ).round(2)

    service_totals = grouped.groupby("service")["active_users"].transform("sum")

    grouped["share_of_active_users"] = (
        grouped["active_users"] / service_totals.clip(lower=1) * 100
    ).round(2)

    return grouped.sort_values(
        ["service", "active_users", "events"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def find_underused_services(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "service",
                "active_users",
                "events",
                "avg_events_per_active_user",
                "underuse_reason",
            ]
        )

    summary = (
        df.groupby("service", as_index=False)
        .agg(
            active_users=("user_id", "nunique"),
            events=("user_id", "size"),
        )
        .sort_values("events")
    )

    summary["avg_events_per_active_user"] = (
        summary["events"] / summary["active_users"].clip(lower=1)
    ).round(2)

    events_threshold = summary["events"].quantile(
        settings.underused_service_quantile
    )
    users_threshold = summary["active_users"].quantile(
        settings.underused_service_quantile
    )
    frequency_threshold = summary["avg_events_per_active_user"].quantile(
        settings.underused_service_quantile
    )

    def build_reason(row: pd.Series) -> str:
        reasons = []

        if row["events"] <= events_threshold:
            reasons.append("faible volume d'événements")

        if row["active_users"] <= users_threshold:
            reasons.append("faible nombre d'utilisateurs actifs")

        if row["avg_events_per_active_user"] <= frequency_threshold:
            reasons.append("faible fréquence d'utilisation")

        return ", ".join(reasons)

    underused = summary[
        (summary["events"] <= events_threshold)
        | (summary["active_users"] <= users_threshold)
        | (summary["avg_events_per_active_user"] <= frequency_threshold)
    ].copy()

    underused["underuse_reason"] = underused.apply(build_reason, axis=1)

    return underused.sort_values(
        ["active_users", "events", "avg_events_per_active_user"]
    ).reset_index(drop=True)

def compute_usage_rate(
        active_users: int,
        eligible_users: int,
    ) -> float | None:
        """Calcule le taux d'utilisation d'un service.

        Formule :
            utilisateurs actifs / utilisateurs éligibles * 100

        Retourne None si le nombre d'utilisateurs éligibles est nul
        ou inconnu.
        """
        if eligible_users <= 0:
            return None

        if active_users < 0:
            raise ValueError("active_users ne peut pas être négatif.")

        if active_users > eligible_users:
            raise ValueError(
                "active_users ne peut pas dépasser eligible_users."
            )

        return round((active_users / eligible_users) * 100, 2)

def inactive_users(df: pd.DataFrame, inactivity_days: int | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["user_id", "department", "last_seen", "inactive_days"])

    effective_days = inactivity_days if inactivity_days is not None else settings.default_inactivity_days
    data = _with_date(df)
    reference_date = data["event_timestamp"].max().normalize()
    last_seen = (
        data.groupby(["user_id", "department"], as_index=False)
        .agg(last_seen=("event_timestamp", "max"))
        .sort_values("last_seen")
    )
    last_seen["inactive_days"] = (reference_date - last_seen["last_seen"].dt.normalize()).dt.days
    return last_seen[last_seen["inactive_days"] >= effective_days]

def compute_usage_frequency(
    df: pd.DataFrame,
) -> dict[str, float]:
    """Calcule la fréquence d'utilisation d'un service."""

    if df.empty:
        return {
            "active_users": 0,
            "total_events": 0,
            "avg_events_per_active_user": 0.0,
            "avg_active_days_per_user": 0.0,
        }

    data = _with_date(df)
    active_users = data["user_id"].nunique()

    if active_users == 0:
        return {
            "active_users": 0,
            "total_events": len(data),
            "avg_events_per_active_user": 0.0,
            "avg_active_days_per_user": 0.0,
        }

    active_days_per_user = (
        data.groupby("user_id")["date"]
        .nunique()
        .sum()
    )

    return {
        "active_users": active_users,
        "total_events": len(data),
        "avg_events_per_active_user": round(len(data) / active_users, 2),
        "avg_active_days_per_user": round(active_days_per_user / active_users, 2),
    }


def compute_advanced_adoption_kpis(metrics: dict) -> dict:
    """Calcule des KPI avancés d'adoption à partir des KPI de base.

    Les KPI attendus dans metrics sont :
    - dau
    - wau
    - mau

    Les valeurs retournées sont exprimées en pourcentage.
    """

    dau = float(metrics.get("dau", 0) or 0)
    wau = float(metrics.get("wau", 0) or 0)
    mau = float(metrics.get("mau", 0) or 0)

    if mau <= 0:
        stickiness = None
        weekly_recurrence = None
    else:
        stickiness = (dau / mau) * 100
        weekly_recurrence = (wau / mau) * 100

    return {
        "stickiness_dau_mau": stickiness,
        "weekly_recurrence_wau_mau": weekly_recurrence,
    }
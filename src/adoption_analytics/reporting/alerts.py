import pandas as pd

from adoption_analytics.metrics.adoption import adoption_timeseries


def build_usage_drop_alerts(df: pd.DataFrame, drop_threshold: float = 0.3) -> list[str]:
    daily = adoption_timeseries(df)
    if daily.empty:
        return []

    alerts: list[str] = []
    for service, service_df in daily.groupby("service"):
        service_df = service_df.sort_values("date").tail(14)
        if len(service_df) < 8:
            continue
        previous_avg = service_df.head(7)["active_users"].mean()
        recent_avg = service_df.tail(7)["active_users"].mean()
        if previous_avg and recent_avg < previous_avg * (1 - drop_threshold):
            drop = (previous_avg - recent_avg) / previous_avg
            alerts.append(f"Baisse d'adoption détectée pour {service}: -{drop:.0%} vs semaine précédente.")
    return alerts

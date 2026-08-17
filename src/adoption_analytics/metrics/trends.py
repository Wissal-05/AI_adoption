import pandas as pd

def build_unified_adoption_trend(
    usage_df: pd.DataFrame,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
    service_bounds: dict[str, tuple[pd.Timestamp, pd.Timestamp]] | None = None
) -> pd.DataFrame:
    """Construit une tendance quotidienne commune DAU / WAU / MAU / événements / fréquence par service."""
    
    required_columns = {"event_timestamp", "user_id", "service"}
    if usage_df.empty or not required_columns.issubset(usage_df.columns):
        return pd.DataFrame(
            columns=["date", "service", "dau", "wau", "mau", "events", "frequency"]
        )

    df = usage_df.copy()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    df = df.dropna(subset=["event_timestamp", "user_id", "service"])

    if df.empty:
        return pd.DataFrame(
            columns=["date", "service", "dau", "wau", "mau", "events", "frequency"]
        )

    df["date"] = df["event_timestamp"].dt.normalize()

    rows = []

    for service, service_df in df.groupby("service"):
        service_df = service_df[["date", "user_id"]].copy()

        daily_users = (
            service_df.groupby("date")["user_id"]
            .agg(lambda users: set(users.dropna()))
            .to_dict()
        )

        daily_events = service_df.groupby("date").size().to_dict()

        if service_bounds and service in service_bounds:
            actual_min, actual_max = service_bounds[service]
            if start_date is not None and end_date is not None:
                eff_start = max(actual_min, start_date.normalize())
                eff_end = min(actual_max, end_date.normalize())
                if eff_start <= eff_end:
                    unique_dates = pd.date_range(eff_start, eff_end)
                else:
                    unique_dates = pd.DatetimeIndex([])
            else:
                unique_dates = pd.date_range(actual_min, actual_max)
        else:
            if start_date is not None and end_date is not None:
                unique_dates = pd.date_range(start_date.normalize(), end_date.normalize())
            else:
                unique_dates = pd.date_range(service_df["date"].min(), service_df["date"].max())

        for current_date in unique_dates:
            day_users = daily_users.get(current_date, set())
            day_events = int(daily_events.get(current_date, 0))

            wau_users = set()
            for date in pd.date_range(current_date - pd.Timedelta(days=6), current_date):
                wau_users.update(daily_users.get(date, set()))

            mau_users = set()
            for date in pd.date_range(current_date - pd.Timedelta(days=29), current_date):
                mau_users.update(daily_users.get(date, set()))

            dau = len(day_users)
            frequency = day_events / dau if dau else 0

            rows.append(
                {
                    "date": current_date,
                    "service": service,
                    "dau": dau,
                    "wau": len(wau_users),
                    "mau": len(mau_users),
                    "events": day_events,
                    "frequency": frequency,
                }
            )

    return pd.DataFrame(rows)

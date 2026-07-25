import pandas as pd


def latest_daily_kpis(df: pd.DataFrame) -> dict[str, int | float | str]:
    if df.empty:
        return {
            "date": "N/A",
            "dau_approx": 0,
            "wau_approx": 0,
            "mau_approx": 0,
            "total_requests": 0,
            "human_requests": 0,
            "page_views": 0,
            "api_requests": 0,
            "errors_4xx": 0,
            "errors_5xx": 0,
            "error_rate": 0.0,
        }

    latest = df.sort_values("date").iloc[-1].to_dict()
    total = latest.get("total_requests", 0) or 0
    latest["error_rate"] = (
        (latest.get("errors_4xx", 0) + latest.get("errors_5xx", 0)) / total if total else 0.0
    )
    return latest


def prepare_daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "dau", "wau", "mau"])

    metric_columns = {
        "dau": "dau" if "dau" in df.columns else "dau_approx",
        "wau": "wau" if "wau" in df.columns else "wau_approx",
        "mau": "mau" if "mau" in df.columns else "mau_approx",
    }

    required_columns = ["date", *metric_columns.values()]
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        return pd.DataFrame(columns=["date", "dau", "wau", "mau"])

    trend = (
        df[required_columns]
        .rename(
            columns={
                metric_columns["dau"]: "dau",
                metric_columns["wau"]: "wau",
                metric_columns["mau"]: "mau",
            }
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    return trend

def route_type_summary(top_routes: pd.DataFrame) -> pd.DataFrame:
    if top_routes.empty:
        return pd.DataFrame(columns=["route_type", "requests"])

    data = top_routes.copy()
    data["route_type"] = data["path"].map(_route_type)
    return data.groupby("route_type", as_index=False)["requests"].sum().sort_values(
        "requests", ascending=False
    )


def _route_type(path: str) -> str:
    value = str(path)
    if value.startswith("/v1/") or value.startswith("/api/"):
        return "API"
    if value.startswith("/_next/") or "." in value.rsplit("/", 1)[-1]:
        return "Static / Next.js"
    if value == "/" or value.startswith("/book") or value.startswith("/search"):
        return "Pages"
    return "Other"

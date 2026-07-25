import re

import pandas as pd

from config.settings import settings


def detect_suspicious_routes(
    df: pd.DataFrame,
    suspicious_patterns: list[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    patterns = suspicious_patterns or settings.suspicious_route_patterns
    pattern = re.compile("|".join(re.escape(item) for item in patterns), flags=re.IGNORECASE)
    detected = df[df["route"].astype(str).str.contains(pattern, na=False)].copy()
    detected["is_error"] = detected["status_code"].between(400, 599)
    detected["risk_label"] = detected["route"].map(lambda route: _label_route(str(route)))
    return detected.sort_values("event_timestamp", ascending=False)


def summarize_security_events(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {"error_events": 0, "unique_ips": 0, "unique_routes": 0}

    return {
        "error_events": int(df["status_code"].between(400, 599).sum()),
        "unique_ips": int(df["source_ip"].nunique()),
        "unique_routes": int(df["route"].nunique()),
    }


def _label_route(route: str) -> str:
    route_lower = route.lower()
    if ".env" in route_lower or "config" in route_lower:
        return "Secret/config probing"
    if "wp-" in route_lower or "phpmyadmin" in route_lower:
        return "CMS/admin probing"
    if "admin" in route_lower:
        return "Admin discovery"
    return "Suspicious route"

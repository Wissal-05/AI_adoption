import pandas as pd
from typing import Any

from adoption_analytics.metrics.adoption import compute_adoption_metrics, compute_advanced_adoption_kpis

def parse_booking_timestamps(series: pd.Series) -> pd.Series:
    """Parse les timestamps Booking aux formats mixtes (avec/sans fraction, avec/sans timezone).
    
    Hypothèse temporelle : Les timestamps naïfs (sans timezone spécifiée) sont
    considérés comme étant en UTC. Le parsing convertit tout en UTC puis
    rend la série naïve (.dt.tz_localize(None)) pour rester compatible
    avec le reste du modèle canonique.
    """
    return pd.to_datetime(series, errors="coerce", format="mixed", utc=True).dt.tz_localize(None)

def _get_reference_date(df: pd.DataFrame, reference_date: pd.Timestamp | None, date_col: str = "event_timestamp") -> pd.Timestamp:
    if reference_date is not None:
        return reference_date
    if df.empty or date_col not in df.columns:
        return pd.Timestamp.now().normalize()
    return parse_booking_timestamps(df[date_col]).max().normalize()


def compute_booking_usage_kpis(
    events_df: pd.DataFrame, 
    reference_date: pd.Timestamp | None = None
) -> dict[str, Any]:
    """Calcule les KPI stratégiques d'usage pour Booking.
    
    Retourne DAU, WAU, MAU inclusifs et leurs KPI avancés,
    ainsi que les nouvelles métriques de jours actifs.
    """
    if events_df.empty:
        return {
            "dau": 0, "wau": 0, "mau": 0,
            "stickiness_dau_mau": None,
            "weekly_recurrence_wau_mau": None,
            "avg_active_days_per_active_user_30d": 0.0,
            "median_active_days_per_active_user_30d": 0.0,
            "observed_usage_intensity_30d": None,
            "technical_event_intensity": 0.0,
            "active_users_full_history": 0,
            "reference_date": reference_date
        }

    # Copie et nettoyage de la date
    data = events_df.copy()
    if "user_id_anonymized" in data.columns and "user_id" not in data.columns:
        data = data.rename(columns={"user_id_anonymized": "user_id"})
    
    data["event_timestamp"] = parse_booking_timestamps(data["event_timestamp"])
    data = data.dropna(subset=["event_timestamp", "user_id"])
    data["date"] = data["event_timestamp"].dt.normalize()
    
    ref_date = _get_reference_date(data, reference_date)
    
    # 1. Base Adoption Metrics (compute_adoption_metrics uses -6 and -29 days logic correctly for inclusive windows)
    base_metrics = compute_adoption_metrics(data, reference_date=ref_date)
    advanced = compute_advanced_adoption_kpis(base_metrics)

    # 2. Fenêtre 30 jours pour la fréquence (MAU window)
    window_days = 30
    window_start = ref_date - pd.Timedelta(days=window_days - 1)
    window_data = data[data["date"] >= window_start]
    
    if window_data.empty:
        avg_active_days = 0.0
        median_active_days = 0.0
        tech_intensity = 0.0
        observed_intensity = None
    else:
        # active days per user in the window
        active_days_per_user = window_data.groupby("user_id")["date"].nunique()
        avg_active_days = round(float(active_days_per_user.mean()), 2)
        median_active_days = float(active_days_per_user.median())
        
        active_users_window = window_data["user_id"].nunique()
        tech_intensity = round(len(window_data) / active_users_window, 2) if active_users_window > 0 else 0.0
        observed_intensity = round((avg_active_days / window_days) * 100, 2)

    return {
        "dau": base_metrics.get("dau", 0),
        "wau": base_metrics.get("wau", 0),
        "mau": base_metrics.get("mau", 0),
        "stickiness_dau_mau": advanced.get("stickiness_dau_mau"),
        "weekly_recurrence_wau_mau": advanced.get("weekly_recurrence_wau_mau"),
        "avg_active_days_per_active_user_30d": avg_active_days,
        "median_active_days_per_active_user_30d": median_active_days,
        "observed_usage_intensity_30d": observed_intensity,
        "technical_event_intensity": tech_intensity,
        "active_users_full_history": data["user_id"].nunique(),
        "reference_date": ref_date
    }


def compute_booking_connection_kpis(
    sessions_df: pd.DataFrame,
    events_df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
    window_days: int = 30
) -> dict[str, Any]:
    """Calcule les KPI de connexion pour Booking sur une fenêtre de temps."""
    if sessions_df.empty:
        return {
            "connected_users_30d": 0,
            "session_count_30d": 0,
            "sessions_per_connected_user_30d": 0.0,
            "connected_users_with_business_activity": 0,
            "business_activity_after_connection_share": 0.0
        }

    # Reference date from sessions if not provided
    ref_date = _get_reference_date(sessions_df, reference_date, "created_at")
    window_start = ref_date - pd.Timedelta(days=window_days - 1)
    
    sess = sessions_df.copy()
    sess["created_at"] = parse_booking_timestamps(sess["created_at"])
    sess["date"] = sess["created_at"].dt.normalize()
    sess_window = sess[sess["date"] >= window_start]
    
    connected_users = sess_window["user_id"].nunique() if "user_id" in sess_window.columns else sess_window["user_id_anonymized"].nunique()
    session_count = len(sess_window)
    sessions_per_user = round(session_count / connected_users, 2) if connected_users > 0 else 0.0
    
    # Check overlap with business events
    connected_users_list = sess_window["user_id"].unique() if "user_id" in sess_window.columns else sess_window["user_id_anonymized"].unique()
    
    ev = events_df.copy()
    if "user_id_anonymized" in ev.columns and "user_id" not in ev.columns:
        ev = ev.rename(columns={"user_id_anonymized": "user_id"})
    ev["event_timestamp"] = parse_booking_timestamps(ev["event_timestamp"])
    ev["date"] = ev["event_timestamp"].dt.normalize()
    ev_window = ev[ev["date"] >= window_start]
    
    if not ev_window.empty and len(connected_users_list) > 0:
        ev_users = set(ev_window["user_id"].unique())
        connected_with_business = len(set(connected_users_list).intersection(ev_users))
    else:
        connected_with_business = 0
        
    share = round((connected_with_business / connected_users * 100), 2) if connected_users > 0 else 0.0
    
    return {
        "connected_users_30d": connected_users,
        "session_count_30d": session_count,
        "sessions_per_connected_user_30d": sessions_per_user,
        "connected_users_with_business_activity": connected_with_business,
        "business_activity_after_connection_share": share
    }


def compute_booking_adoption_by_module(
    events_df: pd.DataFrame,
    eligible_df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
    window_days: int = 30
) -> list[dict[str, Any]]:
    """Calcule l'adoption observée par module Booking sur une fenêtre de temps."""
    ref_date = _get_reference_date(events_df, reference_date)
    window_start = ref_date - pd.Timedelta(days=window_days - 1)
    
    ev = events_df.copy()
    if "user_id_anonymized" in ev.columns and "user_id" not in ev.columns:
        ev = ev.rename(columns={"user_id_anonymized": "user_id"})
    ev["event_timestamp"] = parse_booking_timestamps(ev["event_timestamp"])
    ev["date"] = ev["event_timestamp"].dt.normalize()
    ev_window = ev[ev["date"] >= window_start]
    
    # Active users par module
    module_active_users = {}
    if not ev_window.empty and "module" in ev_window.columns:
        module_active_users = ev_window.groupby("module")["user_id"].nunique().to_dict()
    
    historical_modules = set()
    if not ev.empty and "module" in ev.columns:
        historical_modules = set(ev["module"].dropna().unique())
    
    results = []
    
    # Agrégation des populations éligibles par module (somme sur tous les campus)
    eligible_grouped = {}
    if not eligible_df.empty and "service" in eligible_df.columns:
        eligible_grouped = eligible_df.groupby("service")["eligible_users"].sum().to_dict()
        
    # Liste de tous les modules (dans les events ou dans l'éligibilité)
    all_modules = set(module_active_users.keys()).union(set(eligible_grouped.keys()))
    
    for module in sorted(all_modules):
        active = module_active_users.get(module, 0)
        eligible = eligible_grouped.get(module, 0)
        
        if module not in eligible_grouped or eligible <= 0:
            results.append({
                "module": module,
                "active_users": active,
                "eligible_users": eligible,
                "observed_adoption_rate": None,
                "status": "eligible_population_unavailable"
            })
            continue
            
        if module not in historical_modules:
            results.append({
                "module": module,
                "active_users": None,
                "eligible_users": eligible,
                "observed_adoption_rate": None,
                "status": "telemetry_unavailable"
            })
            continue
            
        rate = round((active / eligible) * 100, 2)
        results.append({
            "module": module,
            "active_users": active,
            "eligible_users": eligible,
            "observed_adoption_rate": rate,
            "status": "available"
        })
            
    return results


def compute_booking_adoption_by_campus(
    events_df: pd.DataFrame,
    eligible_df: pd.DataFrame,
    users_df: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
    window_days: int = 30
) -> list[dict[str, Any]]:
    """Calcule l'adoption observée par campus et par module Booking."""
    ref_date = _get_reference_date(events_df, reference_date)
    window_start = ref_date - pd.Timedelta(days=window_days - 1)
    
    ev = events_df.copy()
    if "user_id_anonymized" in ev.columns and "user_id" not in ev.columns:
        ev = ev.rename(columns={"user_id_anonymized": "user_id"})
        
    usr = users_df.copy()
    if "user_id_anonymized" in usr.columns and "user_id" not in usr.columns:
        usr = usr.rename(columns={"user_id_anonymized": "user_id"})
        
    if not usr.empty:
        ev = ev.merge(usr[["user_id", "campus_name"]], on="user_id", how="left")
        
    ev["event_timestamp"] = parse_booking_timestamps(ev["event_timestamp"])
    ev["date"] = ev["event_timestamp"].dt.normalize()
    ev_window = ev[ev["date"] >= window_start]
    
    active_by_campus_module = {}
    if not ev_window.empty and "module" in ev_window.columns and "campus_name" in ev_window.columns:
        grouped = ev_window.groupby(["module", "campus_name"])["user_id"].nunique().reset_index()
        for _, row in grouped.iterrows():
            active_by_campus_module[(row["module"], row["campus_name"])] = row["user_id"]
            
    has_transport_telemetry = not ev.empty and "module" in ev.columns and "TRANSPORT" in ev["module"].values

    results = []
    
    if not eligible_df.empty and "service" in eligible_df.columns and "campus_name" in eligible_df.columns:
        for _, row in eligible_df.iterrows():
            module = row["service"]
            campus = row["campus_name"]
            eligible = row["eligible_users"]
            active = active_by_campus_module.get((module, campus), 0)
            
            if module == "TRANSPORT" and not has_transport_telemetry:
                results.append({
                    "module": module,
                    "campus": campus,
                    "active_users": active,
                    "eligible_users": eligible,
                    "observed_adoption_rate": None,
                    "status": "telemetry_unavailable"
                })
                continue
                
            if eligible > 0:
                rate = round((active / eligible) * 100, 2)
                results.append({
                    "module": module,
                    "campus": campus,
                    "active_users": active,
                    "eligible_users": eligible,
                    "observed_adoption_rate": rate,
                    "status": "available"
                })
            else:
                results.append({
                    "module": module,
                    "campus": campus,
                    "active_users": active,
                    "eligible_users": eligible,
                    "observed_adoption_rate": None,
                    "status": "eligible_population_unavailable"
                })
                
    return results


def compute_booking_data_quality(
    events_raw: pd.DataFrame,
    sessions_raw: pd.DataFrame,
    users_raw: pd.DataFrame
) -> dict[str, Any]:
    """Génère le rapport de qualité de données Booking."""
    
    event_rows = len(events_raw)
    session_rows = len(sessions_raw)
    
    ev_uid_col = "user_id_anonymized" if "user_id_anonymized" in events_raw.columns else "user_id"
    sess_uid_col = "user_id_anonymized" if "user_id_anonymized" in sessions_raw.columns else "user_id"
    usr_uid_col = "user_id_anonymized" if "user_id_anonymized" in users_raw.columns else "user_id"
    
    unique_event_users = events_raw[ev_uid_col].nunique() if ev_uid_col in events_raw.columns else 0
    unique_session_users = sessions_raw[sess_uid_col].nunique() if sess_uid_col in sessions_raw.columns else 0
    mapped_users = users_raw[usr_uid_col].nunique() if usr_uid_col in users_raw.columns else 0
    
    # Check timestamp parse failures
    event_timestamp_parse_failures = 0
    if "event_timestamp" in events_raw.columns and not events_raw.empty:
        non_null_original = events_raw["event_timestamp"].notna()
        parsed = parse_booking_timestamps(events_raw.loc[non_null_original, "event_timestamp"])
        event_timestamp_parse_failures = parsed.isna().sum()
        
    session_created_at_parse_failures = 0
    if "created_at" in sessions_raw.columns and not sessions_raw.empty:
        non_null_original = sessions_raw["created_at"].notna()
        parsed = parse_booking_timestamps(sessions_raw.loc[non_null_original, "created_at"])
        session_created_at_parse_failures = parsed.isna().sum()
        
    # Couverture
    mapped_set = set(users_raw[usr_uid_col].dropna().unique()) if usr_uid_col in users_raw.columns else set()
    event_users_set = set(events_raw[ev_uid_col].dropna().unique()) if ev_uid_col in events_raw.columns else set()
    session_users_set = set(sessions_raw[sess_uid_col].dropna().unique()) if sess_uid_col in sessions_raw.columns else set()
    
    event_mapped = len(event_users_set.intersection(mapped_set))
    session_mapped = len(session_users_set.intersection(mapped_set))
    
    event_mapping_coverage = round((event_mapped / len(event_users_set) * 100), 2) if event_users_set else 100.0
    session_mapping_coverage = round((session_mapped / len(session_users_set) * 100), 2) if session_users_set else 100.0
    
    # Missing entities
    missing_entity_users = 0
    missing_entity_active_users = 0
    if "entity_names" in users_raw.columns:
        missing_entities_set = set(users_raw[users_raw["entity_names"].isna()][usr_uid_col].unique())
        missing_entity_users = len(missing_entities_set)
        missing_entity_active_users = len(missing_entities_set.intersection(event_users_set))
        
    # Repeated event rows (duplicates based on timestamp, user, action, module)
    possible_repeated_event_rows = 0
    possible_repeated_event_share = 0.0
    
    check_cols = []
    for c in ["event_timestamp", ev_uid_col, "action_name", "module"]:
        if c in events_raw.columns:
            check_cols.append(c)
            
    if check_cols and not events_raw.empty:
        possible_repeated_event_rows = events_raw.duplicated(subset=check_cols, keep="first").sum()
        possible_repeated_event_share = round((possible_repeated_event_rows / event_rows) * 100, 2)
        
    return {
        "event_rows": event_rows,
        "unique_event_users": unique_event_users,
        "session_rows": session_rows,
        "unique_session_users": unique_session_users,
        "mapped_users": mapped_users,
        "event_user_mapping_coverage": event_mapping_coverage,
        "session_user_mapping_coverage": session_mapping_coverage,
        "event_timestamp_parse_failures": int(event_timestamp_parse_failures),
        "session_created_at_parse_failures": int(session_created_at_parse_failures),
        "missing_entity_users": missing_entity_users,
        "missing_entity_active_users": missing_entity_active_users,
        "possible_repeated_event_rows": possible_repeated_event_rows,
        "possible_repeated_event_share": possible_repeated_event_share
    }

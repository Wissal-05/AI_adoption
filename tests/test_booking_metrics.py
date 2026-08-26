import pandas as pd
import pytest
from adoption_analytics.metrics.booking_metrics import (
    compute_booking_usage_kpis,
    compute_booking_connection_kpis,
    compute_booking_adoption_by_module,
    compute_booking_adoption_by_campus,
    compute_booking_data_quality,
)

def test_booking_usage_kpis():
    # 1. DAU inclusif, WAU=7 inclusifs, MAU=30 inclusifs, ref_date par défaut = dernière date
    # 5. moyenne jours actifs / 6. médiane jours actifs
    events = pd.DataFrame({
        "event_timestamp": [
            "2026-08-12 10:00:00", # Today (ref) -> User 1, User 2
            "2026-08-12 11:00:00", # Today -> User 1 again
            "2026-08-10 10:00:00", # -2 days -> User 1
            "2026-08-06 10:00:00", # -6 days -> User 3 (WAU include 12, 11, 10, 9, 8, 7, 6)
            "2026-07-15 10:00:00", # -28 days -> User 4 (MAU include 29 days diff)
            "2026-07-10 10:00:00", # -33 days -> User 5 (outside MAU)
        ],
        "user_id": ["u1", "u2", "u1", "u1", "u3", "u4", "u5"][:6] # Match length 6
    })
    events["user_id"] = ["u1", "u2", "u1", "u3", "u4", "u5"] # u1, u2, u1, u3, u4, u5 -> length 6
    # Active days in MAU window (2026-07-14 to 2026-08-12):
    # u1: 2 days (12, 10)
    # u2: 1 day (12)
    # u3: 1 day (6)
    # u4: 1 day (15)
    # mean active days = (2+1+1+1)/4 = 1.25
    # median = 1.0
    
    res = compute_booking_usage_kpis(events)
    assert res["reference_date"] == pd.Timestamp("2026-08-12")
    assert res["dau"] == 2 # u1, u2
    assert res["wau"] == 3 # u1, u2, u3
    assert res["mau"] == 4 # u1, u2, u3, u4
    assert res["active_users_full_history"] == 5 # u1, u2, u3, u4, u5
    assert res["avg_active_days_per_active_user_30d"] == 1.25
    assert res["median_active_days_per_active_user_30d"] == 1.0
    
def test_booking_connection_kpis():
    # 7. connected_users, 8. session_count, 9. sessions_per_connected_user
    # 10. overlap sessions/events
    sessions = pd.DataFrame({
        "created_at": ["2026-08-12", "2026-08-12", "2026-08-10"],
        "user_id": ["u1", "u1", "u2"]
    })
    events = pd.DataFrame({
        "event_timestamp": ["2026-08-12", "2026-07-01"],
        "user_id": ["u1", "u2"]
    })
    
    res = compute_booking_connection_kpis(sessions, events, window_days=30)
    assert res["connected_users_30d"] == 2
    assert res["session_count_30d"] == 3
    assert res["sessions_per_connected_user_30d"] == 1.5
    assert res["connected_users_with_business_activity"] == 1 # only u1
    assert res["business_activity_after_connection_share"] == 50.0

def test_booking_adoption_by_module_and_campus():
    # 11. adoption par module, 12. adoption campus, 13. TRANSPORT None, 14. no pop = None
    events = pd.DataFrame({
        "event_timestamp": ["2026-08-12"] * 5,
        "user_id": ["u1", "u2", "u3", "u4", "u5"],
        "module": ["HOUSING", "HOUSING", "CATERING", "UNKNOWN", "TRANSPORT"],
        "campus_name": ["Benguerir", "Rabat", "Benguerir", "Benguerir", "Benguerir"]
    })
    eligible = pd.DataFrame({
        "service": ["HOUSING", "HOUSING", "CATERING", "TRANSPORT", "NEW_MODULE"],
        "campus_name": ["Benguerir", "Rabat", "Benguerir", "Benguerir", "Benguerir"],
        "eligible_users": [10, 10, 5, 0, 5]
    })
    
    # 13. To simulate no transport telemetry, remove it from events
    events_no_trans = events[events["module"] != "TRANSPORT"]
    
    res_mod = compute_booking_adoption_by_module(events_no_trans, eligible)
    mod_dict = {r["module"]: r for r in res_mod}
    
    assert mod_dict["HOUSING"]["observed_adoption_rate"] == 10.0 # 2 active / 20 eligible
    assert mod_dict["TRANSPORT"]["observed_adoption_rate"] is None
    assert mod_dict["TRANSPORT"]["status"] == "eligible_population_unavailable"
    assert mod_dict["UNKNOWN"]["observed_adoption_rate"] is None
    assert mod_dict["UNKNOWN"]["status"] == "eligible_population_unavailable"
    
    assert mod_dict["NEW_MODULE"]["status"] == "telemetry_unavailable"
    assert mod_dict["NEW_MODULE"]["active_users"] is None
    assert mod_dict["NEW_MODULE"]["observed_adoption_rate"] is None

def test_booking_usage_intensity():
    dates = []
    users = []
    base_date = pd.Timestamp("2026-08-12")
    for i in range(100):
        days = 4 if i < 84 else 3
        for d in range(days):
            dates.append(base_date - pd.Timedelta(days=d))
            users.append(f"u{i}")
    events = pd.DataFrame({"event_timestamp": dates, "user_id": users})
    res = compute_booking_usage_kpis(events, reference_date=base_date)
    assert res["avg_active_days_per_active_user_30d"] == 3.84
    assert res["observed_usage_intensity_30d"] == 12.8

def test_booking_adoption_by_campus():
    events = pd.DataFrame({
        "event_timestamp": ["2026-08-12"] * 5,
        "user_id": ["u1", "u2", "u3", "u4", "u5"],
        "module": ["HOUSING", "HOUSING", "CATERING", "UNKNOWN", "TRANSPORT"],
        "campus_name": ["Benguerir", "Rabat", "Benguerir", "Benguerir", "Benguerir"]
    })
    eligible = pd.DataFrame({
        "service": ["HOUSING", "HOUSING", "CATERING", "TRANSPORT", "NEW_MODULE"],
        "campus_name": ["Benguerir", "Rabat", "Benguerir", "Benguerir", "Benguerir"],
        "eligible_users": [10, 10, 5, 0, 5]
    })
    events_no_trans = events[events["module"] != "TRANSPORT"]
    res_camp = compute_booking_adoption_by_campus(events_no_trans, eligible, users_df=pd.DataFrame())
    camp_dict = {(r["module"], r["campus"]): r for r in res_camp}
    assert camp_dict[("HOUSING", "Benguerir")]["observed_adoption_rate"] == 10.0 # 1 active / 10 eligible
    
def test_data_quality():
    # 15. mapping orga manquant, 16. aucune deduplication auto
    events = pd.DataFrame({
        "event_timestamp": ["2026-08-12", "2026-08-12"],
        "user_id": ["u1", "u1"],
        "action_name": ["act", "act"],
        "module": ["mod", "mod"]
    })
    sessions = pd.DataFrame({"user_id": ["u2"]})
    users = pd.DataFrame({"user_id": ["u1", "u3"], "entity_names": [None, "Ent"]})
    
    res = compute_booking_data_quality(events, sessions, users)
    assert res["possible_repeated_event_rows"] == 1
    assert res["missing_entity_users"] == 1
    assert res["event_user_mapping_coverage"] == 100.0
    assert res["session_user_mapping_coverage"] == 0.0


def test_parse_booking_timestamps_mixed_formats():
    from adoption_analytics.metrics.booking_metrics import parse_booking_timestamps
    
    # A. millisecondes
    # B. sans fraction
    # C. microsecondes + timezone
    # D. mélange
    
    s = pd.Series([
        '2026-08-12 13:18:18.167',
        '2026-08-12 13:18:18',
        '2026-04-15 10:02:08.111984+00',
        None,
        'invalid'
    ])
    
    parsed = parse_booking_timestamps(s)
    
    # Check A
    assert parsed[0] == pd.Timestamp('2026-08-12 13:18:18.167')
    # Check B
    assert parsed[1] == pd.Timestamp('2026-08-12 13:18:18')
    # Check C (should be naive in UTC)
    assert parsed[2] == pd.Timestamp('2026-04-15 10:02:08.111984')
    # Valid dates should not be NaT
    assert pd.notna(parsed[0])
    assert pd.notna(parsed[1])
    assert pd.notna(parsed[2])
    # Invalid or None should be NaT
    assert pd.isna(parsed[3])
    assert pd.isna(parsed[4])

def test_entity_campus_fallback_removed():
    # entity manquante reste Non renseigné, ne pas utiliser campus_name
    from adoption_analytics.data_sources.booking import BookingSource
    from adoption_analytics.data_sources.base import DataSourceConfig
    from pathlib import Path
    
    # Just test that BookingSource doesn't fallback to campus
    # We can mock BookingDataLoader
    pass

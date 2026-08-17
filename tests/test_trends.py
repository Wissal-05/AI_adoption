import pandas as pd
import pytest
from adoption_analytics.metrics.trends import build_unified_adoption_trend

def test_build_unified_adoption_trend():
    usage_df = pd.DataFrame({
        "service": ["Booking", "Booking", "Booking", "Learning Center"],
        "user_id": [1, 2, 1, 3],
        "event_timestamp": [
            pd.Timestamp("2026-08-01 10:00:00"),
            pd.Timestamp("2026-08-01 11:00:00"),
            pd.Timestamp("2026-08-02 10:00:00"),
            pd.Timestamp("2026-08-01 09:00:00")
        ]
    })
    
    # Sans bounds => date min/max de chaque service par défaut
    df = build_unified_adoption_trend(usage_df)
    
    booking_df = df[df["service"] == "Booking"]
    assert len(booking_df) == 2
    
    # 2026-08-01 : users 1, 2 => dau = 2, events = 2
    day1 = booking_df[booking_df["date"] == pd.Timestamp("2026-08-01")].iloc[0]
    assert day1["dau"] == 2
    assert day1["events"] == 2
    
    # 2026-08-02 : user 1 => dau = 1, events = 1, wau = 2 (users 1, 2)
    day2 = booking_df[booking_df["date"] == pd.Timestamp("2026-08-02")].iloc[0]
    assert day2["dau"] == 1
    assert day2["events"] == 1
    assert day2["wau"] == 2
    
def test_build_unified_adoption_trend_empty():
    df = build_unified_adoption_trend(pd.DataFrame())
    assert df.empty
    assert list(df.columns) == ["date", "service", "dau", "wau", "mau", "events", "frequency"]

def test_build_unified_adoption_trend_bounds_zero_fill():
    usage_df = pd.DataFrame({
        "service": ["Learning Center", "Learning Center"],
        "user_id": [1, 1],
        "event_timestamp": [
            pd.Timestamp("2026-08-01 10:00:00"),
            pd.Timestamp("2026-08-03 10:00:00")
        ]
    })
    
    # On simule un service bound plus large
    bounds = {"Learning Center": (pd.Timestamp("2026-07-31"), pd.Timestamp("2026-08-04"))}
    
    df = build_unified_adoption_trend(usage_df, service_bounds=bounds)
    
    assert len(df) == 5 # 31, 1, 2, 3, 4
    
    # 2026-08-02 is a silent day internally
    day2 = df[df["date"] == pd.Timestamp("2026-08-02")].iloc[0]
    assert day2["dau"] == 0
    assert day2["events"] == 0

def test_build_unified_adoption_trend_multi_service():
    usage_df = pd.DataFrame({
        "service": ["A", "B"],
        "user_id": [1, 1],
        "event_timestamp": [
            pd.Timestamp("2026-08-01 10:00:00"),
            pd.Timestamp("2026-08-01 10:00:00")
        ]
    })
    
    df = build_unified_adoption_trend(usage_df)
    assert len(df) == 2
    assert "A" in df["service"].values
    assert "B" in df["service"].values

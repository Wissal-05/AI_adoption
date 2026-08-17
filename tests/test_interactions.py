import pandas as pd
import pytest
from adoption_analytics.metrics.interactions import compute_top_interactions

def test_booking_reach():
    usage_df = pd.DataFrame({
        "service": ["Booking", "Booking", "Booking"],
        "action": ["A", "A", "B"],
        "user_id": [1, 2, 1]
    })
    
    df, reach_type, lims = compute_top_interactions(usage_df, pd.DataFrame(), service="Booking", measure="reach", limit=10)
    
    assert reach_type == "distinct_users"
    assert len(df) == 2
    assert df.iloc[0]["interaction"] == "A"
    assert df.iloc[0]["reach"] == 2
    assert df.iloc[0]["events"] == 2
    assert df.iloc[0]["events_share_pct"] == 66.67
    
def test_booking_events_sorting():
    usage_df = pd.DataFrame({
        "service": ["Booking"] * 5,
        "action": ["A", "B", "B", "B", "C"],
        "user_id": [1, 2, 2, 2, 3] # A: 1 user, B: 1 user, C: 1 user
    })
    # If sorted by reach: all have 1 user
    # If sorted by events: B has 3, A has 1, C has 1
    df, _, _ = compute_top_interactions(usage_df, pd.DataFrame(), service="Booking", measure="events", limit=10)
    
    assert df.iloc[0]["interaction"] == "B"
    assert df.iloc[0]["events"] == 3
    assert df.iloc[0]["reach"] == 1

def test_limit_applied():
    usage_df = pd.DataFrame({
        "service": ["Booking"] * 10,
        "action": [f"A{i}" for i in range(10)],
        "user_id": [i for i in range(10)]
    })
    df, _, _ = compute_top_interactions(usage_df, pd.DataFrame(), service="Booking", measure="reach", limit=5)
    assert len(df) == 5

def test_learning_center_source_ips():
    web_logs = pd.DataFrame({
        "service": ["Learning Center", "Learning Center", "Learning Center"],
        "route": ["/home", "/home", "/about"],
        "source_ip": ["ip1", "ip2", "ip1"],
        "analytics_eligible": [True, True, True]
    })
    
    df, reach_type, lims = compute_top_interactions(pd.DataFrame(), web_logs, service="Learning Center", measure="reach", limit=10)
    
    assert reach_type == "distinct_source_ips"
    assert len(df) == 2
    assert df.iloc[0]["interaction"] == "/home"
    assert df.iloc[0]["reach"] == 2
    assert "source" in str(lims).lower()
    
def test_learning_center_bot_exclusion():
    web_logs = pd.DataFrame({
        "service": ["Learning Center", "Learning Center"],
        "route": ["/home", "/bot"],
        "source_ip": ["ip1", "ip2"],
        "analytics_eligible": [True, False]
    })
    
    df, _, _ = compute_top_interactions(pd.DataFrame(), web_logs, service="Learning Center", measure="reach", limit=10)
    
    assert len(df) == 1
    assert df.iloc[0]["interaction"] == "/home"

def test_ecommerce_demo_distinct_users():
    usage_df = pd.DataFrame({
        "service": ["Ecommerce Demo", "Ecommerce Demo"],
        "page": ["/product/1", "/product/1"],
        "user_id": [10, 10]
    })
    
    df, reach_type, lims = compute_top_interactions(usage_df, pd.DataFrame(), service="Ecommerce Demo", measure="reach", limit=10)
    
    assert reach_type == "distinct_users"
    assert len(df) == 1
    assert df.iloc[0]["reach"] == 1
    assert df.iloc[0]["events"] == 2

def test_empty_dataset():
    df, reach_type, lims = compute_top_interactions(pd.DataFrame(), pd.DataFrame(), service="Booking", measure="reach", limit=10)
    assert df.empty
    assert list(df.columns) == ["interaction", "reach", "events", "events_share_pct"]

import pytest
import pandas as pd
from datetime import date, datetime

def compute_staleness_days(available_end, window_end_date):
    available_end_ts = pd.Timestamp(available_end).normalize()
    window_end_ts = pd.Timestamp(window_end_date).normalize()
    return (window_end_ts - available_end_ts).days

def test_staleness_different_types():
    # available_end as pd.Timestamp, window_end_date as datetime.date
    available_end = pd.Timestamp("2026-07-23 14:30:00")
    window_end = date(2026, 8, 10)
    
    staleness = compute_staleness_days(available_end, window_end)
    assert staleness == 18 # 18 days difference
    assert staleness > 7

def test_staleness_same_date():
    # staleness = 0
    available_end = pd.Timestamp("2026-08-10 09:15:00")
    window_end = date(2026, 8, 10)
    
    staleness = compute_staleness_days(available_end, window_end)
    assert staleness == 0

def test_staleness_greater_than_7():
    # fin fenêtre 10/08/2026
    # dernière donnée 23/07/2026
    # staleness > 7
    available_end = pd.Timestamp("2026-07-23 23:59:59")
    window_end = date(2026, 8, 10)
    
    staleness = compute_staleness_days(available_end, window_end)
    assert staleness > 7

import pytest
import pandas as pd
from datetime import date

from adoption_analytics.ui.filters import (
    DateWindow,
    get_available_date_bounds,
    resolve_period,
    apply_date_filter,
    get_previous_window,
    compute_period_change,
)

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "event_timestamp": pd.to_datetime([
            "2023-10-01", "2023-10-15", "2023-11-01", "2023-11-15", "2023-11-30"
        ]),
        "value": [10, 20, 30, 40, 50]
    })


def test_toute_la_periode(sample_df):
    start, end = get_available_date_bounds(sample_df)
    window = resolve_period("Toute la période disponible", start, end)
    assert window.start_date == pd.Timestamp("2023-10-01")
    assert window.end_date == pd.Timestamp("2023-11-30")


def test_7_derniers_jours(sample_df):
    start, end = get_available_date_bounds(sample_df)
    window = resolve_period("7 derniers jours", start, end)
    assert window.end_date == pd.Timestamp("2023-11-30")
    # 2023-11-30 - 6 days = 2023-11-24
    assert window.start_date == pd.Timestamp("2023-11-24")


def test_30_derniers_jours(sample_df):
    start, end = get_available_date_bounds(sample_df)
    window = resolve_period("30 derniers jours", start, end)
    assert window.end_date == pd.Timestamp("2023-11-30")
    # 2023-11-30 - 29 days = 2023-11-01
    assert window.start_date == pd.Timestamp("2023-11-01")


def test_60_derniers_jours(sample_df):
    start, end = get_available_date_bounds(sample_df)
    window = resolve_period("60 derniers jours", start, end)
    assert window.end_date == pd.Timestamp("2023-11-30")
    # 2023-11-30 - 59 days = 2023-10-02 -> But wait! 'start' cannot be before available_start. 
    # The max logic is applied: max(2023-10-02, 2023-10-01) = 2023-10-02.
    assert window.start_date == pd.Timestamp("2023-10-02")


def test_periode_personnalisee(sample_df):
    start, end = get_available_date_bounds(sample_df)
    custom_start = date(2023, 10, 10)
    custom_end = date(2023, 10, 20)
    window = resolve_period(
        "Période personnalisée", start, end,
        custom_start=custom_start, custom_end=custom_end
    )
    assert window.start_date == pd.Timestamp("2023-10-10")
    assert window.end_date == pd.Timestamp("2023-10-20")


def test_date_debut_sup_date_fin(sample_df):
    start, end = get_available_date_bounds(sample_df)
    custom_start = date(2023, 10, 20)
    custom_end = date(2023, 10, 10)
    with pytest.raises(ValueError, match="La date de début doit précéder la date de fin."):
        resolve_period(
            "Période personnalisée", start, end,
            custom_start=custom_start, custom_end=custom_end
        )


def test_filtre_dataframe(sample_df):
    start, end = get_available_date_bounds(sample_df)
    window = resolve_period("30 derniers jours", start, end)
    # Window is 2023-11-01 to 2023-11-30
    filtered_df = apply_date_filter(sample_df, window)
    assert len(filtered_df) == 3
    assert filtered_df["value"].tolist() == [30, 40, 50]


def test_previous_window():
    window = DateWindow(
        start_date=pd.Timestamp("2023-11-01"),
        end_date=pd.Timestamp("2023-11-30"),
        label="Test"
    )
    prev_window = get_previous_window(window)
    # duration is 30 days
    # prev_end = 2023-10-31
    # prev_start = 2023-10-31 - 29 days = 2023-10-02
    assert prev_window.end_date == pd.Timestamp("2023-10-31")
    assert prev_window.start_date == pd.Timestamp("2023-10-02")
    assert prev_window.label == "Période précédente"


def test_compute_period_change():
    assert compute_period_change(150, 100) == 50.0
    assert compute_period_change(50, 100) == -50.0
    assert compute_period_change(None, 100) is None
    assert compute_period_change(150, None) is None


def test_previous_value_zero():
    assert compute_period_change(150, 0) is None

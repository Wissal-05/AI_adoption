import pandas as pd
import pytest

from adoption_analytics.metrics.adoption import compute_adoption_metrics, find_underused_services,  compute_usage_rate, compute_usage_frequency, find_underused_services, departmental_breakdown


def test_compute_adoption_metrics_counts_active_windows():
    df = pd.DataFrame(
        [
            {
                "event_timestamp": "2026-07-20 10:00:00",
                "user_id": "u1",
                "department": "IT",
                "service": "Learning Center",
                "action": "login",
                "source": "learning_center",
            },
            {
                "event_timestamp": "2026-07-15 10:00:00",
                "user_id": "u2",
                "department": "IT",
                "service": "Booking",
                "action": "visit",
                "source": "booking",
            },
        ]
    )

    metrics = compute_adoption_metrics(df, reference_date=pd.Timestamp("2026-07-20"))

    assert metrics["dau"] == 1
    assert metrics["wau"] == 2
    assert metrics["mau"] == 2


def test_find_underused_services_returns_lowest_usage():
    df = pd.DataFrame(
        [
            {"user_id": "u1", "service": "Learning Center"},
            {"user_id": "u2", "service": "Learning Center"},
            {"user_id": "u3", "service": "Booking"},
        ]
    )

    underused = find_underused_services(df)

    assert "Booking" in underused["service"].tolist()

def test_compute_usage_rate():
    result = compute_usage_rate(
        active_users=50,
        eligible_users=100,
    )

    assert result == 50.0


def test_compute_usage_rate_with_no_active_users():
    result = compute_usage_rate(
        active_users=0,
        eligible_users=100,
    )

    assert result == 0.0


def test_compute_usage_rate_with_no_eligible_users():
    result = compute_usage_rate(
        active_users=10,
        eligible_users=0,
    )

    assert result is None


def test_compute_usage_rate_rejects_negative_active_users():
    with pytest.raises(ValueError):
        compute_usage_rate(
            active_users=-1,
            eligible_users=100,
        )


def test_compute_usage_rate_rejects_more_active_than_eligible_users():
    with pytest.raises(ValueError):
        compute_usage_rate(
            active_users=120,
            eligible_users=100,
        )

def test_compute_usage_frequency():
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u2", "u2"],
            "event_timestamp": [
                "2026-07-01 10:00:00",
                "2026-07-01 11:00:00",
                "2026-07-01 12:00:00",
                "2026-07-02 09:00:00",
                "2026-07-02 10:00:00",
            ],
            "service": ["learning_center"] * 5,
        }
    )

    result = compute_usage_frequency(df)

    assert result["active_users"] == 2
    assert result["total_events"] == 5
    assert result["avg_events_per_active_user"] == 2.5
    assert result["avg_active_days_per_user"] == 1.5


def test_compute_usage_frequency_with_empty_dataframe():
    result = compute_usage_frequency(pd.DataFrame())

    assert result["active_users"] == 0
    assert result["total_events"] == 0
    assert result["avg_events_per_active_user"] == 0.0
    assert result["avg_active_days_per_user"] == 0.0

def test_find_underused_services_includes_frequency_reason():
    df = pd.DataFrame(
        {
            "user_id": [
                "u1",
                "u2",
                "u3",
                "u4",
                "u5",
                "u6",
                "u7",
                "u8",
                "u9",
                "u10",
            ],
            "event_timestamp": ["2026-07-01 10:00:00"] * 10,
            "service": [
                "learning_center",
                "learning_center",
                "learning_center",
                "learning_center",
                "learning_center",
                "booking",
                "booking",
                "teams",
                "teams",
                "teams",
            ],
        }
    )

    result = find_underused_services(df)

    assert not result.empty
    assert "avg_events_per_active_user" in result.columns
    assert "underuse_reason" in result.columns


def test_find_underused_services_with_empty_dataframe():
    result = find_underused_services(pd.DataFrame())

    assert result.empty
    assert list(result.columns) == [
        "service",
        "active_users",
        "events",
        "avg_events_per_active_user",
        "underuse_reason",
    ]

def test_departmental_breakdown_includes_share_of_active_users():
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u2", "u3", "u1", "u4"],
            "event_timestamp": [
                "2026-07-01 10:00:00",
                "2026-07-01 11:00:00",
                "2026-07-01 12:00:00",
                "2026-07-02 09:00:00",
                "2026-07-02 10:00:00",
            ],
            "department": [
                "IT",
                "IT",
                "Finance",
                "IT",
                "Finance",
            ],
            "service": ["Learning Center"] * 5,
        }
    )

    result = departmental_breakdown(df)

    assert list(result.columns) == [
        "department",
        "service",
        "active_users",
        "events",
        "avg_events_per_user",
        "share_of_active_users",
    ]

    it_row = result[result["department"] == "IT"].iloc[0]
    finance_row = result[result["department"] == "Finance"].iloc[0]

    assert it_row["active_users"] == 2
    assert it_row["events"] == 3
    assert it_row["avg_events_per_user"] == 1.5
    assert it_row["share_of_active_users"] == 50.0

    assert finance_row["active_users"] == 2
    assert finance_row["events"] == 2
    assert finance_row["avg_events_per_user"] == 1.0
    assert finance_row["share_of_active_users"] == 50.0


def test_departmental_breakdown_with_empty_dataframe():
    result = departmental_breakdown(pd.DataFrame())

    assert result.empty
    assert list(result.columns) == [
        "department",
        "service",
        "active_users",
        "events",
        "avg_events_per_user",
        "share_of_active_users",
    ]


def test_departmental_breakdown_with_missing_columns():
    result = departmental_breakdown(
        pd.DataFrame(
            {
                "user_id": ["u1", "u2"],
                "service": ["Learning Center", "Learning Center"],
            }
        )
    )

    assert result.empty


def test_compute_advanced_adoption_kpis():
    from adoption_analytics.metrics.adoption import compute_advanced_adoption_kpis

    result = compute_advanced_adoption_kpis(
        {
            "dau": 10,
            "wau": 50,
            "mau": 100,
        }
    )

    assert result["stickiness_dau_mau"] == 10.0
    assert result["weekly_recurrence_wau_mau"] == 50.0


def test_compute_advanced_adoption_kpis_handles_zero_mau():
    from adoption_analytics.metrics.adoption import compute_advanced_adoption_kpis

    result = compute_advanced_adoption_kpis(
        {
            "dau": 10,
            "wau": 50,
            "mau": 0,
        }
    )

    assert result["stickiness_dau_mau"] is None
    assert result["weekly_recurrence_wau_mau"] is None


def test_compute_advanced_adoption_kpis_handles_missing_values():
    from adoption_analytics.metrics.adoption import compute_advanced_adoption_kpis

    result = compute_advanced_adoption_kpis({})

    assert result["stickiness_dau_mau"] is None
    assert result["weekly_recurrence_wau_mau"] is None
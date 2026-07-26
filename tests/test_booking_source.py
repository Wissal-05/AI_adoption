import pandas as pd

from adoption_analytics.data_sources.base import DataSourceConfig
from adoption_analytics.data_sources.booking import BookingSource


def test_booking_source_maps_usage_events_to_canonical_schema(tmp_path):
    path = tmp_path / "usage-events-60d.csv"

    raw = pd.DataFrame(
        {
            "event_id_anonymized": ["e1"],
            "user_id_anonymized": ["u1"],
            "event_time": ["2026-07-23 10:00:00"],
            "action_type": ["CREATE_HOUSING"],
            "entity_name": [None],
            "campus_name": ["Benguerir"],
        }
    )

    raw.to_csv(path, index=False)

    source = BookingSource(
        DataSourceConfig(
            name="booking",
            path=path,
            kind="usage",
        )
    )

    result = source.load()

    assert len(result) == 1
    assert result.iloc[0]["user_id"] == "u1"
    assert result.iloc[0]["department"] == "Benguerir"
    assert result.iloc[0]["service"] == "Booking"
    assert result.iloc[0]["action"] == "CREATE_HOUSING"
    assert result.iloc[0]["source"] == "booking_usage_events"
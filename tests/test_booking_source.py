import pandas as pd

from adoption_analytics.data_sources.base import DataSourceConfig
from adoption_analytics.data_sources.booking import BookingSource


def test_booking_source_maps_usage_events_to_canonical_schema(tmp_path):
    path = tmp_path / "booking_events_120d.csv"
    users_path = tmp_path / "booking_users_mapping.csv"

    raw = pd.DataFrame(
        {
            "business_object_id_anonymized": ["e1"],
            "user_id_anonymized": ["u1"],
            "event_timestamp": ["2026-07-23 10:00:00"],
            "action_name": ["CREATE_HOUSING"],
            "module": ["HOUSING"],
            "business_status": ["SUCCESS"],
            "source": ["user_activities"]
        }
    )
    raw.to_csv(path, index=False)
    
    users = pd.DataFrame({
        "user_id_anonymized": ["u1"],
        "entity_names": [None],
        "campus_name": ["Benguerir"],
    })
    users.to_csv(users_path, index=False)

    source = BookingSource(
        DataSourceConfig(
            name="booking",
            path=tmp_path,
            kind="usage",
        )
    )

    result = source.load()

    assert len(result) == 1
    assert result.iloc[0]["user_id"] == "u1"
    assert result.iloc[0]["department"] == "Non renseigné"
    assert result.iloc[0]["service"] == "Booking"
    assert result.iloc[0]["action"] == "CREATE_HOUSING"
    assert result.iloc[0]["source"] == "user_activities"
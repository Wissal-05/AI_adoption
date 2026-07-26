import pandas as pd

from adoption_analytics.data_sources.base import (
    DataSource,
    normalize_usage_events,
    read_csv_if_exists,
)


class BookingSource(DataSource):
    """Connecteur Booking vers le schéma canonique UsageEvent."""

    def load(self) -> pd.DataFrame:
        raw = read_csv_if_exists(self.config.path)

        if raw.empty:
            return normalize_usage_events(
                raw,
                source=self.config.name,
                service="Booking",
            )

        mapped = pd.DataFrame(
            {
                "event_timestamp": raw["event_time"],
                "user_id": raw["user_id_anonymized"],
                "department": (
                    raw["entity_name"]
                    .fillna(raw["campus_name"])
                    .fillna("Unknown")
                ),
                "service": "Booking",
                "action": raw["action_type"],
                "source": "booking_usage_events",
                "event_id": raw["event_id_anonymized"],
            }
        )

        return normalize_usage_events(
            mapped,
            source=self.config.name,
            service="Booking",
        )
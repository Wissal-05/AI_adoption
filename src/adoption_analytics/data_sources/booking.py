import pandas as pd

from adoption_analytics.data_sources.base import DataSource, normalize_usage_events, read_csv_if_exists


class BookingSource(DataSource):
    def load(self) -> pd.DataFrame:
        raw = read_csv_if_exists(self.config.path)
        return normalize_usage_events(raw, source=self.config.name, service="Booking")

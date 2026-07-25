import pandas as pd

from adoption_analytics.data_sources.base import DataSource, normalize_web_logs, read_csv_if_exists


class WebLogSource(DataSource):
    def load(self) -> pd.DataFrame:
        raw = read_csv_if_exists(self.config.path)
        return normalize_web_logs(raw, source=self.config.name)

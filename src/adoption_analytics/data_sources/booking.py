import pandas as pd
from pathlib import Path
from adoption_analytics.data_sources.base import (
    DataSource,
    normalize_usage_events,
    read_csv_if_exists,
)

class BookingDataLoader:
    """Charge les quatre fichiers canoniques 120d Booking."""
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        
    def load_events(self) -> pd.DataFrame:
        return read_csv_if_exists(self.data_dir / "booking_events_120d.csv")
        
    def load_sessions(self) -> pd.DataFrame:
        return read_csv_if_exists(self.data_dir / "booking_sessions_120d.csv")
        
    def load_users(self) -> pd.DataFrame:
        return read_csv_if_exists(self.data_dir / "booking_users_mapping.csv")
        
    def load_eligible_population(self) -> pd.DataFrame:
        return read_csv_if_exists(self.data_dir / "booking_eligible_population.csv")


class BookingSource(DataSource):
    """Connecteur Booking vers le schéma canonique UsageEvent."""

    def load(self) -> pd.DataFrame:
        # data_dir is derived from config.path.parent assuming config.path points to an old file
        # or we just use config.path if it's the directory. Let's handle both.
        path = Path(self.config.path)
        data_dir = path if path.is_dir() else path.parent
        
        loader = BookingDataLoader(data_dir)
        events = loader.load_events()
        users = loader.load_users()
        
        if events.empty:
            return normalize_usage_events(events, source=self.config.name, service="Booking")
            
        # Rename columns to match schemas
        mapped = pd.DataFrame({
            "event_timestamp": events["event_timestamp"],
            "user_id": events["user_id_anonymized"],
            "action": events["action_name"],
            "module": events["module"],
            "business_status": events["business_status"],
            "source": events["source"],
            "service": "Booking",
        })
        
        if not users.empty:
            # Join with users to get organization data
            users_mapped = users.rename(columns={
                "user_id_anonymized": "user_id",
                "entity_names": "entity_name"
            })
            mapped = mapped.merge(users_mapped, on="user_id", how="left")
            mapped["department"] = mapped["entity_name"].fillna("Non renseigné")
        else:
            mapped["department"] = "Non renseigné"
            
        return normalize_usage_events(
            mapped,
            source=self.config.name,
            service="Booking",
        )
"""Fixtures partagées pour tous les tests.

Centralise la création de DataFrames de test conformes aux schémas canoniques,
évitant la duplication dans chaque fichier de test.
"""

import pytest
import pandas as pd


@pytest.fixture
def sample_usage_df() -> pd.DataFrame:
    """DataFrame d'usage conforme au schéma UsageEvent avec données variées."""
    return pd.DataFrame(
        [
            {
                "event_timestamp": "2026-07-20 10:00:00",
                "user_id": "u1",
                "department": "IT",
                "service": "Learning Center",
                "action": "login",
                "source": "learning_center_nginx",
            },
            {
                "event_timestamp": "2026-07-20 11:00:00",
                "user_id": "u2",
                "department": "RH",
                "service": "Learning Center",
                "action": "visit",
                "source": "learning_center_nginx",
            },
            {
                "event_timestamp": "2026-07-15 10:00:00",
                "user_id": "u2",
                "department": "RH",
                "service": "Booking",
                "action": "reservation",
                "source": "booking",
            },
            {
                "event_timestamp": "2026-06-01 09:00:00",
                "user_id": "u3",
                "department": "Finance",
                "service": "Learning Center",
                "action": "visit",
                "source": "learning_center_nginx",
            },
        ]
    )


@pytest.fixture
def sample_web_logs_df() -> pd.DataFrame:
    """DataFrame de logs web conforme au schéma WebLog avec routes variées."""
    return pd.DataFrame(
        [
            {
                "event_timestamp": "2026-07-20 12:00:00",
                "source_ip": "192.168.1.100",
                "route": "/wp-admin",
                "status_code": 404,
                "user_agent": "Mozilla/5.0",
                "source": "learning_center_nginx",
            },
            {
                "event_timestamp": "2026-07-20 12:05:00",
                "source_ip": "10.0.0.50",
                "route": "/.env",
                "status_code": 403,
                "user_agent": "curl/7.68.0",
                "source": "learning_center_nginx",
            },
            {
                "event_timestamp": "2026-07-20 12:10:00",
                "source_ip": "192.168.1.100",
                "route": "/",
                "status_code": 200,
                "user_agent": "Mozilla/5.0",
                "source": "learning_center_nginx",
            },
        ]
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """DataFrame vide générique pour tester les cas limites."""
    return pd.DataFrame()

import pandas as pd

from adoption_analytics.metrics.security import detect_suspicious_routes


def test_detect_suspicious_routes_flags_known_attack_paths():
    df = pd.DataFrame(
        [
            {
                "event_timestamp": "2026-07-20 10:00:00",
                "source_ip": "198.51.100.10",
                "route": "/.env",
                "status_code": 404,
                "user_agent": "scanner",
                "source": "web",
            },
            {
                "event_timestamp": "2026-07-20 10:01:00",
                "source_ip": "198.51.100.11",
                "route": "/courses",
                "status_code": 200,
                "user_agent": "browser",
                "source": "web",
            },
        ]
    )

    detected = detect_suspicious_routes(df)

    assert len(detected) == 1
    assert detected.iloc[0]["risk_label"] == "Secret/config probing"

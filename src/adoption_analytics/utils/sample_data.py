from datetime import datetime, timedelta
import random

import pandas as pd


def build_sample_usage_events() -> pd.DataFrame:
    random.seed(42)
    departments = ["IT", "Learning", "Operations", "Finance", "Research"]
    services = ["Learning Center", "Booking"]
    actions = ["login", "view", "search", "download", "reservation"]
    start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=59)

    rows = []
    for day in range(60):
        for user_index in range(1, 46):
            if random.random() < 0.55:
                service = random.choice(services)
                rows.append(
                    {
                        "event_timestamp": start + timedelta(days=day, hours=random.randint(0, 9)),
                        "user_id": f"user_{user_index:03d}",
                        "department": random.choice(departments),
                        "service": service,
                        "action": random.choice(actions),
                        "source": service.lower().replace(" ", "_"),
                    }
                )
    return pd.DataFrame(rows)


def build_sample_web_logs() -> pd.DataFrame:
    random.seed(7)
    routes = ["/", "/courses", "/booking", "/api/events", "/wp-admin", "/.env", "/phpmyadmin", "/admin"]
    status_codes = [200, 200, 200, 302, 401, 403, 404, 500]
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=14)

    rows = []
    for index in range(220):
        suspicious = random.random() < 0.18
        route = random.choice(routes[-4:] if suspicious else routes[:4])
        rows.append(
            {
                "event_timestamp": start + timedelta(hours=index),
                "source_ip": f"198.51.100.{random.randint(1, 80)}",
                "route": route,
                "status_code": random.choice(status_codes if suspicious else [200, 200, 302, 404]),
                "user_agent": "Mozilla/5.0" if not suspicious else "scanner",
                "source": "edge_logs",
            }
        )
    return pd.DataFrame(rows)

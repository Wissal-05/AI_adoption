import pandas as pd

from adoption_analytics.metrics.learning_center import latest_daily_kpis, route_type_summary


def test_latest_daily_kpis_computes_error_rate():
    df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-07-20"),
                "dau_approx": 10,
                "wau_approx": 20,
                "mau_approx": 30,
                "total_requests": 100,
                "human_requests": 80,
                "page_views": 70,
                "api_requests": 10,
                "errors_4xx": 4,
                "errors_5xx": 1,
            }
        ]
    )

    latest = latest_daily_kpis(df)

    assert latest["error_rate"] == 0.05


def test_route_type_summary_groups_learning_center_paths():
    df = pd.DataFrame(
        [
            {"path": "/", "requests": 10},
            {"path": "/v1/api/v1/resa", "requests": 5},
            {"path": "/_next/data/build/fr/search.json", "requests": 3},
        ]
    )

    summary = route_type_summary(df)

    assert set(summary["route_type"]) == {"Pages", "API", "Static / Next.js"}

import pandas as pd

from adoption_analytics.data_sources.matomo import (
    classify_matomo_page_action,
    load_latest_processed_matomo_usage_events,
    load_matomo_usage_for_dashboard,
    normalize_matomo_live_visits,
    normalize_matomo_page_urls,
)


def test_classifies_matomo_page_actions():
    assert classify_matomo_page_action("/product/demo-product-001") == "product_view"
    assert classify_matomo_page_action("/checkout/step1") == "checkout_visit"
    assert classify_matomo_page_action("/signin") == "auth_visit"
    assert classify_matomo_page_action("/shop") == "catalog_view"
    assert classify_matomo_page_action("/featured") == "catalog_view"
    assert classify_matomo_page_action("/recommended") == "catalog_view"
    assert classify_matomo_page_action("/") == "page_view"


def test_normalizes_matomo_page_urls_to_common_model():
    page_urls_df = pd.DataFrame(
        [
            {
                "label": "/shop",
                "Actions_PageUrl": "/shop",
                "url": "http://localhost:3000/shop",
                "nb_hits": 3,
                "nb_visits": 2,
                "nb_uniq_visitors": 2,
                "sum_time_spent": 9,
                "avg_time_on_page": 3,
                "bounce_rate": "0%",
                "exit_rate": "0%",
            },
            {
                "label": "/product/demo-product-001",
                "Actions_PageUrl": "/product/demo-product-001",
                "url": "http://localhost:3000/product/demo-product-001",
                "nb_hits": 2,
                "nb_visits": 1,
                "nb_uniq_visitors": 1,
                "sum_time_spent": 10,
                "avg_time_on_page": 5,
                "bounce_rate": "0%",
                "exit_rate": "0%",
            },
        ]
    )

    visits_summary = {
        "nb_uniq_visitors": 2,
        "nb_visits": 2,
        "nb_actions": 5,
    }

    usage_df = normalize_matomo_page_urls(
        page_urls_df=page_urls_df,
        visits_summary=visits_summary,
        export_date="2026-08-05",
        service_name="Ecommerce Demo",
    )

    assert len(usage_df) == 5

    assert set(usage_df["service"]) == {"Ecommerce Demo"}
    assert set(usage_df["source"]) == {"matomo"}
    assert set(usage_df["event_type"]) == {"page_view"}

    assert usage_df["user_id"].nunique() == 2
    assert usage_df["session_id"].nunique() == 2

    assert "event_timestamp" in usage_df.columns
    assert "date" in usage_df.columns
    assert "event_date_local" in usage_df.columns
    assert "department" in usage_df.columns
    assert "entity" in usage_df.columns
    assert "campus" in usage_df.columns

    assert "catalog_view" in usage_df["action"].values
    assert "product_view" in usage_df["action"].values

    assert set(usage_df["department"]) == {"Non renseigné"}
    assert set(usage_df["entity"]) == {"Non renseigné"}
    assert set(usage_df["campus"]) == {"Non renseigné"}


def test_normalization_uses_nb_hits_as_number_of_events():
    page_urls_df = pd.DataFrame(
        [
            {
                "label": "/recommended",
                "Actions_PageUrl": "/recommended",
                "url": "http://localhost:3000/recommended",
                "nb_hits": 7,
                "nb_visits": 2,
                "nb_uniq_visitors": 2,
                "sum_time_spent": 11,
                "avg_time_on_page": 2,
                "bounce_rate": "0%",
                "exit_rate": "0%",
            }
        ]
    )

    usage_df = normalize_matomo_page_urls(
        page_urls_df=page_urls_df,
        visits_summary={"nb_uniq_visitors": 2, "nb_visits": 2},
        export_date="2026-08-05",
        service_name="Ecommerce Demo",
    )

    assert len(usage_df) == 7
    assert set(usage_df["action"]) == {"catalog_view"}
    assert set(usage_df["page"]) == {"/recommended"}

def test_loads_latest_processed_matomo_usage_events(tmp_path):
    processed_file = tmp_path / "usage_events_20260805_120000.csv"

    df = pd.DataFrame(
        [
            {
                "event_timestamp": "2026-08-05 00:00:00",
                "date": "2026-08-05",
                "event_date_local": "2026-08-05",
                "user_id": "matomo_visitor_001",
                "service": "Ecommerce Demo",
                "action": "catalog_view",
                "page": "/shop",
                "url": "http://localhost:3000/shop",
                "source": "matomo",
                "session_id": "matomo_visit_001",
                "event_type": "page_view",
                "department": "Non renseigné",
                "entity": "Non renseigné",
                "campus": "Non renseigné",
                "nb_visits": 2,
                "nb_uniq_visitors": 2,
                "nb_hits": 3,
                "sum_time_spent": 9,
                "avg_time_on_page": 3,
                "bounce_rate": "0%",
                "exit_rate": "0%",
                "normalization_note": "test",
            }
        ]
    )

    df.to_csv(processed_file, index=False, encoding="utf-8")

    usage_df = load_latest_processed_matomo_usage_events(tmp_path)

    assert len(usage_df) == 1
    assert usage_df.iloc[0]["service"] == "Ecommerce Demo"
    assert usage_df.iloc[0]["source"] == "matomo"
    assert usage_df.iloc[0]["action"] == "catalog_view"
    assert usage_df.iloc[0]["page"] == "/shop"
    assert pd.api.types.is_datetime64_any_dtype(usage_df["event_timestamp"])


def test_load_matomo_usage_for_dashboard_prefers_processed_files(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir(parents=True)

    processed_file = processed_dir / "usage_events_20260805_120000.csv"

    df = pd.DataFrame(
        [
            {
                "event_timestamp": "2026-08-05 00:00:00",
                "date": "2026-08-05",
                "event_date_local": "2026-08-05",
                "user_id": "matomo_visitor_001",
                "service": "Ecommerce Demo",
                "action": "product_view",
                "page": "/product/demo-product-001",
                "url": "http://localhost:3000/product/demo-product-001",
                "source": "matomo",
                "session_id": "matomo_visit_001",
                "event_type": "page_view",
                "department": "Non renseigné",
                "entity": "Non renseigné",
                "campus": "Non renseigné",
                "nb_visits": 1,
                "nb_uniq_visitors": 1,
                "nb_hits": 1,
                "sum_time_spent": 3,
                "avg_time_on_page": 3,
                "bounce_rate": "0%",
                "exit_rate": "0%",
                "normalization_note": "test",
            }
        ]
    )

    df.to_csv(processed_file, index=False, encoding="utf-8")

    usage_df = load_matomo_usage_for_dashboard(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        service_name="Ecommerce Demo",
    )

    assert len(usage_df) == 1
    assert usage_df.iloc[0]["service"] == "Ecommerce Demo"
    assert usage_df.iloc[0]["action"] == "product_view"


def test_load_matomo_usage_for_dashboard_returns_empty_without_files(tmp_path):
    usage_df = load_matomo_usage_for_dashboard(
        raw_dir=tmp_path / "missing_raw",
        processed_dir=tmp_path / "missing_processed",
        service_name="Ecommerce Demo",
    )

    assert usage_df.empty


def test_normalizes_matomo_live_visits_to_common_model():
    live_visits = [
        {
            "visitorId": "abc123",
            "idVisit": "1001",
            "deviceType": "Desktop",
            "browserName": "Chrome",
            "operatingSystemName": "Windows",
            "country": "Morocco",
            "referrerType": "direct",
            "actionDetails": [
                {
                    "type": "action",
                    "url": "http://localhost:3000/shop",
                    "pageTitle": "Shop | Salinaka",
                    "timestamp": 1785888000,
                    "timeSpent": 5,
                },
                {
                    "type": "action",
                    "url": "http://localhost:3000/product/demo-product-001",
                    "pageTitle": "View Clear Vision Classic",
                    "timestamp": 1785888005,
                    "timeSpent": 12,
                },
                {
                    "type": "action",
                    "url": "http://localhost:3000/checkout/step1",
                    "pageTitle": "Checkout",
                    "timestamp": 1785888017,
                    "timeSpent": 3,
                },
            ],
        }
    ]

    usage_df = normalize_matomo_live_visits(
        live_visits=live_visits,
        export_date="2026-08-05",
        service_name="Ecommerce Demo",
    )

    assert len(usage_df) == 3
    assert set(usage_df["service"]) == {"Ecommerce Demo"}
    assert set(usage_df["source"]) == {"matomo_live"}
    assert set(usage_df["event_type"]) == {"page_view"}
    assert usage_df["user_id"].nunique() == 1
    assert usage_df["session_id"].nunique() == 1

    assert "catalog_view" in usage_df["action"].values
    assert "product_view" in usage_df["action"].values
    assert "checkout_visit" in usage_df["action"].values

    assert "/shop" in usage_df["page"].values
    assert "/product/demo-product-001" in usage_df["page"].values
    assert "/checkout/step1" in usage_df["page"].values


def test_normalizes_empty_matomo_live_visits():
    usage_df = normalize_matomo_live_visits(
        live_visits=[],
        export_date="2026-08-05",
        service_name="Ecommerce Demo",
    )

    assert usage_df.empty
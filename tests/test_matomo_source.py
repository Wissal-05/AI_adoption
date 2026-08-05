import pandas as pd

from adoption_analytics.data_sources.matomo import (
    classify_matomo_page_action,
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
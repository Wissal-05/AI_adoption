"""Tests des connecteurs de sources de données."""

import pandas as pd
import pytest

from adoption_analytics.data_sources.base import normalize_usage_events, normalize_web_logs
from adoption_analytics.schemas.usage_event import USAGE_COLUMNS
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS


class TestNormalizeUsageEvents:
    def test_returns_canonical_columns(self):
        raw = pd.DataFrame(
            [{"timestamp": "2026-07-20", "user": "u1", "dept": "IT", "app": "LC", "event": "login"}]
        )
        result = normalize_usage_events(raw, source="test")
        assert list(result.columns) == USAGE_COLUMNS

    def test_empty_df_returns_empty_with_schema(self):
        result = normalize_usage_events(pd.DataFrame(), source="test")
        assert result.empty
        assert list(result.columns) == USAGE_COLUMNS

    def test_fills_missing_optional_columns(self):
        raw = pd.DataFrame([{"event_timestamp": "2026-07-20", "user_id": "u1"}])
        result = normalize_usage_events(raw, source="test", service="MyService")
        assert result.iloc[0]["service"] == "MyService"
        assert result.iloc[0]["action"] == "visit"
        assert result.iloc[0]["department"] == "Unknown"

    def test_drops_rows_with_null_timestamps(self):
        raw = pd.DataFrame(
            [
                {"event_timestamp": "invalid-date", "user_id": "u1"},
                {"event_timestamp": "2026-07-20", "user_id": "u2"},
            ]
        )
        result = normalize_usage_events(raw, source="test")
        assert len(result) == 1
        assert result.iloc[0]["user_id"] == "u2"


class TestNormalizeWebLogs:
    def test_returns_canonical_columns(self):
        raw = pd.DataFrame(
            [{"timestamp": "2026-07-20", "ip": "1.2.3.4", "path": "/wp-admin", "status": 404}]
        )
        result = normalize_web_logs(raw, source="test")
        assert list(result.columns) == WEB_LOG_COLUMNS

    def test_empty_df_returns_empty_with_schema(self):
        result = normalize_web_logs(pd.DataFrame(), source="test")
        assert result.empty
        assert list(result.columns) == WEB_LOG_COLUMNS

    def test_status_code_is_integer(self):
        raw = pd.DataFrame(
            [{"event_timestamp": "2026-07-20", "source_ip": "1.2.3.4", "route": "/test", "status_code": "200"}]
        )
        result = normalize_web_logs(raw, source="test")
        assert result["status_code"].dtype in (int, "int64", "int32")

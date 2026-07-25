"""Tests de la couche services."""

import pandas as pd
import pytest

from adoption_analytics.services.security_service import SecurityService
from adoption_analytics.services.dashboard_service import DashboardService

class TestSecurityService:
    def test_analyze_empty_logs_returns_zeros(self):
        vm = SecurityService.analyze(pd.DataFrame())
        assert vm.total_suspicious == 0
        assert vm.summary["unique_ips"] == 0
        assert vm.summary["unique_routes"] == 0

    def test_analyze_detects_suspicious_routes(self, sample_web_logs_df):
        vm = SecurityService.analyze(sample_web_logs_df)
        assert vm.total_suspicious >= 2  # /wp-admin et /.env
        assert len(vm.top_routes) > 0
        assert len(vm.top_ips) > 0

    def test_analyze_non_suspicious_routes_returns_zero(self):
        clean_logs = pd.DataFrame(
            [
                {
                    "event_timestamp": pd.Timestamp("2026-07-20"),
                    "source_ip": "1.2.3.4",
                    "route": "/about",
                    "status_code": 200,
                    "user_agent": "Mozilla",
                    "source": "test",
                }
            ]
        )
        vm = SecurityService.analyze(clean_logs)
        assert vm.total_suspicious == 0

    def test_analyze_top_routes_has_correct_columns(self, sample_web_logs_df):
        vm = SecurityService.analyze(sample_web_logs_df)
        if not vm.top_routes.empty:
            assert "route" in vm.top_routes.columns
            assert "requests" in vm.top_routes.columns

    def test_analyze_top_ips_has_correct_columns(self, sample_web_logs_df):
        vm = SecurityService.analyze(sample_web_logs_df)
        if not vm.top_ips.empty:
            assert "source_ip" in vm.top_ips.columns
            assert "requests" in vm.top_ips.columns


class TestDashboardService:
    def test_apply_filters_returns_subset(self, sample_usage_df):
        from adoption_analytics.services.dashboard_service import DashboardService

        filtered = DashboardService.apply_filters(
            sample_usage_df,
            services=["Learning Center"],
            departments=["IT"],
        )
        assert not filtered.empty
        assert filtered["service"].unique().tolist() == ["Learning Center"]
        assert filtered["department"].unique().tolist() == ["IT"]

    def test_apply_filters_empty_df_returns_empty(self, empty_df):
        from adoption_analytics.services.dashboard_service import DashboardService

        result = DashboardService.apply_filters(empty_df, services=["LC"], departments=["IT"])
        assert result.empty

    def test_learning_center_view_uses_official_adoption_keys(
        self,
        sample_usage_df,
        monkeypatch,
    ):
        service = DashboardService()

        fake_data = type(
            "FakeDashboardData",
            (),
            {
                "usage_events": sample_usage_df,
                "learning_center_daily": pd.DataFrame(),
                "learning_center_top_routes": pd.DataFrame(),
                "learning_center_source_dir": "test",
            },
        )()

        monkeypatch.setattr(service, "_data", fake_data)

        vm = service.get_learning_center_view()

        assert "dau" in vm.latest_kpis
        assert "wau" in vm.latest_kpis
        assert "mau" in vm.latest_kpis
        assert "dau_approx" not in vm.latest_kpis
        assert "wau_approx" not in vm.latest_kpis
        assert "mau_approx" not in vm.latest_kpis

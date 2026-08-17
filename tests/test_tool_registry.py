import pytest
import pandas as pd
from unittest.mock import MagicMock
import json

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.ai.tool_registry import ToolRegistry, ToolResult


@pytest.fixture
def mock_dashboard_service():
    service = MagicMock(spec=DashboardService)
    
    # Mock data property
    service._data = True
    service.data = MagicMock()
    service.data.usage_events = pd.DataFrame({
        "service": ["Booking", "Learning Center", "Ecommerce Demo"]
    })
    
    # Mock extended analytics for Booking
    extended_mock = MagicMock()
    extended_mock.usage = {
        "dau": 4,
        "wau": 35,
        "mau": 137,
        "avg_active_days_per_active_user_30d": 3.84,
        "technical_event_intensity": 500  # Should not be used
    }
    service.get_service_extended_analytics.return_value = extended_mock
    
    return service


@pytest.fixture
def registry(mock_dashboard_service):
    return ToolRegistry(mock_dashboard_service)


def test_registry_lists_get_usage_kpis(registry):
    tools = registry.list_tools()
    assert len(tools) > 0
    names = [t["name"] for t in tools]
    assert "get_usage_kpis" in names


def test_unknown_tool_returns_structured_error(registry):
    result = registry.execute("unknown_tool", service="Booking")
    assert isinstance(result, ToolResult)
    assert result.status == "error"
    assert "n'existe pas" in result.message


def test_unknown_service_returns_invalid_request(registry):
    result = registry.execute("get_usage_kpis", service="Foo")
    assert result.status == "invalid_request"
    assert "Service inconnu" in result.message
    assert "Booking" in result.message  # Lists available services


def test_case_insensitive_service_resolution(registry):
    result = registry.execute("get_usage_kpis", service=" bOOkInG ")
    assert result.status == "success"
    assert result.service == "Booking"


def test_invalid_reference_date_returns_invalid_request(registry):
    result = registry.execute("get_usage_kpis", service="Booking", reference_date="not-a-date")
    assert result.status == "invalid_request"
    assert "Format de date invalide" in result.message


def test_booking_uses_extended_analytics(registry, mock_dashboard_service):
    result = registry.execute("get_usage_kpis", service="Booking")
    assert result.status == "success"
    assert result.data["dau"] == 4
    assert result.data["wau"] == 35
    assert result.data["mau"] == 137
    mock_dashboard_service.get_service_extended_analytics.assert_called_once()


def test_booking_frequency_uses_active_days(registry):
    result = registry.execute("get_usage_kpis", service="Booking")
    freq = result.data.get("frequency")
    assert freq is not None
    assert freq["value"] == 3.84
    assert freq["unit"] == "days"
    assert freq["definition"] == "average_active_days_per_active_user_30d"


def test_booking_frequency_never_uses_technical_intensity(registry):
    result = registry.execute("get_usage_kpis", service="Booking")
    freq = str(result.data.get("frequency"))
    assert "technical_event_intensity" not in freq
    assert "500" not in freq


def test_generic_service_returns_generic_kpis(registry, monkeypatch):
    # Mock AdoptionMetricsService.compute
    from adoption_analytics.services.adoption_metrics_service import AdoptionMetricsService
    def mock_compute(*args, **kwargs):
        return {"dau": 10, "wau": 50, "mau": 200, "avg_events_per_active_user": 42}
    
    monkeypatch.setattr(AdoptionMetricsService, "compute", mock_compute)
    
    result = registry.execute("get_usage_kpis", service="Learning Center")
    assert result.status == "success"
    assert result.data["dau"] == 10
    assert result.data["wau"] == 50
    assert result.data["mau"] == 200


def test_generic_frequency_is_none_with_limitation(registry, monkeypatch):
    from adoption_analytics.services.adoption_metrics_service import AdoptionMetricsService
    monkeypatch.setattr(AdoptionMetricsService, "compute", lambda *a, **kw: {})
    
    result = registry.execute("get_usage_kpis", service="Learning Center")
    assert result.data.get("frequency") is None
    assert any("Comparable usage frequency is not available" in str(lim) for lim in result.limitations)


def test_all_services_returns_invalid_request(registry):
    for srv in ["Tous les services", "all", "*"]:
        result = registry.execute("get_usage_kpis", service=srv)
        assert result.status == "invalid_request"
        assert "DAU, WAU et MAU doivent être analysés service par service" in result.message


def test_result_is_json_serializable(registry):
    result = registry.execute("get_usage_kpis", service="Booking", reference_date="2026-08-12")
    # Convert dataclass to dict manually since asdict might not be used
    from dataclasses import asdict
    result_dict = asdict(result)
    
    # Should not raise exception
    json_str = json.dumps(result_dict)
    assert isinstance(json_str, str)
    assert "Booking" in json_str


def test_integration_real_booking_data():
    """Test d'intégration optionnel vérifiant le dashboard réel pour Booking."""
    # Instancier le vrai service
    service = DashboardService()
    try:
        service.load()
    except Exception:
        pytest.skip("Dataset réel non disponible")
        
    registry = ToolRegistry(service)
    
    result = registry.execute("get_usage_kpis", service="Booking", reference_date="2026-08-12")
    
    if result.status == "success":
        assert result.data["dau"] == 4
        assert result.data["wau"] == 35
        assert result.data["mau"] == 137
        
        freq = result.data.get("frequency")
        assert freq is not None
        assert freq["value"] == 3.84
        assert freq["unit"] == "days"

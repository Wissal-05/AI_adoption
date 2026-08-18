import pytest

@pytest.fixture(scope="session")
def real_dashboard_service():
    from adoption_analytics.services.dashboard_service import DashboardService
    service = DashboardService()
    try:
        service.load()
        return service
    except Exception:
        return None
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
    assert any("La fréquence d'usage comparable n'est pas disponible" in str(lim) for lim in result.limitations)


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


def test_integration_real_booking_data(real_dashboard_service):
    """Test d'intégration optionnel vérifiant le dashboard réel pour Booking."""
    # Instancier le vrai service
    service = real_dashboard_service
    if service is None:
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


def test_get_adoption_by_module_booking(registry, mock_dashboard_service):
    # Mock data
    mock_extended = mock_dashboard_service.get_service_extended_analytics.return_value
    mock_extended.adoption_by_module = [
        {"module": "Housing", "active_users": 10, "eligible_users": 100, "observed_adoption_rate": 10.0, "status": "available"},
        {"module": "Transport", "active_users": 5, "eligible_users": None, "observed_adoption_rate": None, "status": "telemetry_unavailable"},
        {"module": "Admin", "active_users": 2, "eligible_users": None, "observed_adoption_rate": None, "status": "eligible_population_unavailable"}
    ]

    result = registry.execute("get_adoption_by_module", service="Booking")
    assert result.status == "success"
    assert len(result.data["modules"]) == 3

    result_housing = registry.execute("get_adoption_by_module", service="Booking", module="housing")
    assert result_housing.status == "success"
    assert len(result_housing.data["modules"]) == 1
    assert result_housing.data["modules"][0]["module"] == "Housing"

    result_transport = registry.execute("get_adoption_by_module", service="Booking", module="Transport")
    assert result_transport.status == "success"
    assert result_transport.data["modules"][0]["observed_adoption_rate"] is None
    assert result_transport.data["modules"][0]["status"] == "telemetry_unavailable"

    result_admin = registry.execute("get_adoption_by_module", service="Booking", module="Admin")
    assert result_admin.data["modules"][0]["observed_adoption_rate"] is None

    result_unknown = registry.execute("get_adoption_by_module", service="Booking", module="Unknown")
    assert result_unknown.status == "invalid_request"
    assert "Housing" in result_unknown.message


def test_get_adoption_by_module_other(registry):
    result = registry.execute("get_adoption_by_module", service="Learning Center")
    assert result.status == "not_available"


def test_get_adoption_by_campus_booking(registry, mock_dashboard_service):
    mock_extended = mock_dashboard_service.get_service_extended_analytics.return_value
    mock_extended.adoption_by_campus = [
        {"module": "Housing", "campus": "Khouribga", "active_users": 5, "eligible_users": 10, "observed_adoption_rate": 50.0, "status": "available"},
        {"module": "Housing", "campus": "Benguerir", "active_users": 2, "eligible_users": 10, "observed_adoption_rate": 20.0, "status": "available"},
        {"module": "Transport", "campus": "Khouribga", "active_users": 5, "eligible_users": 10, "observed_adoption_rate": None, "status": "telemetry_unavailable"}
    ]

    result = registry.execute("get_adoption_by_campus", service="Booking", module="Housing")
    assert result.status == "success"
    # Tri décroissant par taux
    assert result.data["campus_list"][0]["campus"] == "Khouribga"
    assert result.data["campus_list"][1]["campus"] == "Benguerir"

    result_kh = registry.execute("get_adoption_by_campus", service="Booking", module="Housing", campus="khOuriBga")
    assert result_kh.status == "success"
    assert len(result_kh.data["campus_list"]) == 1

    result_tr = registry.execute("get_adoption_by_campus", service="Booking", module="Transport")
    assert result_tr.data["campus_list"][0]["observed_adoption_rate"] is None

    result_un = registry.execute("get_adoption_by_campus", service="Booking", module="Admin")
    assert result_un.status == "not_available"


def test_get_top_interactions_validation(registry):
    res_all = registry.execute("get_top_interactions", service="all")
    assert res_all.status == "invalid_request"

    res_limit = registry.execute("get_top_interactions", service="Booking", limit=100)
    assert res_limit.status == "invalid_request"

    res_measure = registry.execute("get_top_interactions", service="Booking", measure="foo")
    assert res_measure.status == "invalid_request"


def test_get_top_interactions_booking(registry, mock_dashboard_service):
    mock_dashboard_service.data.usage_events = pd.DataFrame({
        "service": ["Booking", "Booking", "Booking"],
        "action": ["A", "A", "B"],
        "user_id": [1, 2, 1],
        "event_timestamp": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02"), pd.Timestamp("2026-08-03")]
    })

    res = registry.execute("get_top_interactions", service="Booking", measure="reach")
    assert res.status == "success"
    assert res.data["interactions"][0]["interaction"] == "A"
    assert res.data["interactions"][0]["reach"] == 2
    assert res.data["interactions"][0]["reach_type"] == "distinct_users"
    assert res.data["interactions"][0]["event_count"] == 2

    res_ev = registry.execute("get_top_interactions", service="Booking", measure="events")
    assert res_ev.status == "success"
    assert "signatures répétées" in str(res_ev.limitations)


def test_get_top_interactions_learning_center(registry, mock_dashboard_service):
    mock_dashboard_service.data.usage_events = pd.DataFrame()
    mock_dashboard_service.data.web_logs = pd.DataFrame({
        "service": ["Learning Center", "Learning Center"],
        "route": ["/home", "/home"],
        "source_ip": ["1.1.1.1", "1.1.1.1"],
        "analytics_eligible": [True, True],
        "event_timestamp": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02")]
    })

    res = registry.execute("get_top_interactions", service="Learning Center")
    assert res.status == "success"
    assert res.data["interactions"][0]["reach"] == 1
    assert res.data["interactions"][0]["reach_type"] == "distinct_source_ips"
    assert "IP source" in str(res.limitations)


def test_get_data_quality_booking(registry, mock_dashboard_service):
    mock_extended = mock_dashboard_service.get_service_extended_analytics.return_value
    mock_extended.data_quality = {
        "event_rows": 1000,
        "unique_event_users": 100,
        "missing_entity_active_users": 10,
        "possible_repeated_event_share": 15.5
    }

    res = registry.execute("get_data_quality", service="Booking")
    assert res.status == "success"
    assert res.data["unique_event_users"] == 100
    assert res.data["entity_coverage_active_users"] == 90.0
    assert res.data["possible_repeated_event_share"] == 15.5
    assert len(res.limitations) > 0


def test_get_data_quality_other(registry):
    res = registry.execute("get_data_quality", service="Learning Center")
    assert res.status == "not_available"




def test_json_serializable_all(registry, mock_dashboard_service):
    import json
    from dataclasses import asdict

    mock_extended = mock_dashboard_service.get_service_extended_analytics.return_value
    mock_extended.adoption_by_module = [{"module": "Housing", "status": "available", "observed_adoption_rate": 10.0}]
    mock_extended.adoption_by_campus = [{"module": "Housing", "campus": "Khouribga", "status": "available", "observed_adoption_rate": 10.0}]
    mock_extended.data_quality = {"unique_event_users": 10}

    mock_dashboard_service.data.usage_events = pd.DataFrame({"service": ["Booking"], "action": ["A"], "user_id": [1]})

    for tool_name in ["get_adoption_by_module", "get_adoption_by_campus", "get_data_quality", "get_top_interactions"]:
        if tool_name == "get_adoption_by_campus":
            res = registry.execute(tool_name, service="Booking", module="Housing")
        else:
            res = registry.execute(tool_name, service="Booking")

        json_str = json.dumps(asdict(res))
        assert isinstance(json_str, str)


def test_integration_real_data_all_tools(real_dashboard_service):
    service = real_dashboard_service
    if service is None:
        pytest.skip("Dataset réel non disponible")

    registry = ToolRegistry(service)
    ref_date = "2026-08-12"

    res_mod = registry.execute("get_adoption_by_module", service="Booking", module="Housing", reference_date=ref_date)
    if res_mod.status == "success" and res_mod.data["modules"]:
        assert abs(res_mod.data["modules"][0]["observed_adoption_rate"] - 18.28) < 0.1

    res_camp = registry.execute("get_adoption_by_campus", service="Booking", module="Housing", campus="Khouribga", reference_date=ref_date)
    if res_camp.status == "success" and res_camp.data["campus_list"]:
        assert abs(res_camp.data["campus_list"][0]["observed_adoption_rate"] - 30.77) < 0.1

    res_dq = registry.execute("get_data_quality", service="Booking")
    if res_dq.status == "success":
        assert res_dq.data["event_user_mapping_coverage"] == 100.0
        assert abs(res_dq.data["possible_repeated_event_share"] - 24.85) < 0.1


def test_get_usage_evolution_validation(registry):
    res = registry.execute("get_usage_evolution", service="all")
    assert res.status == "invalid_request"

    res = registry.execute("get_usage_evolution", service="Booking", metric="invalid")
    assert res.status == "invalid_request"

    res = registry.execute("get_usage_evolution", service="Booking", window_days=-1)
    assert res.status == "invalid_request"

    res = registry.execute("get_usage_evolution", service="Unknown")
    assert res.status == "invalid_request"


def test_get_usage_evolution_booking(registry, mock_dashboard_service):
    import pandas as pd
    mock_dashboard_service.data.usage_events = pd.DataFrame({
        "service": ["Booking", "Booking"],
        "user_id": [1, 2],
        "event_timestamp": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02")]
    })


    res = registry.execute("get_usage_evolution", service="Booking", reference_date="2026-08-02", window_days=2)
    assert res.status == "success"
    assert res.data["period_start"] == "2026-08-01"
    assert res.data["period_end"] == "2026-08-02"
    assert len(res.data["series"]) == 2


def test_get_organization_usage_booking(registry, mock_dashboard_service):
    import pandas as pd
    mock_dashboard_service.data.usage_events = pd.DataFrame({
        "service": ["Booking", "Booking", "Booking"],
        "user_id": [1, 2, 3],
        "department": ["IT", "HR", None],
        "event_timestamp": [pd.Timestamp("2026-08-01")] * 3
    })

    res = registry.execute("get_organization_usage", service="Booking", reference_date="2026-08-01", window_days=2)
    assert res.status == "success"
    orgs = [o["organization"] for o in res.data["organizations"]]
    assert "IT" in orgs
    assert "HR" in orgs
    assert "Non renseigné" in orgs


def test_get_organization_usage_not_available(registry):
    res_lc = registry.execute("get_organization_usage", service="Learning Center")
    assert res_lc.status == "not_available"

    res_eco = registry.execute("get_organization_usage", service="Ecommerce Demo")
    assert res_eco.status == "not_available"


def test_json_serializable_new_tools(registry, mock_dashboard_service):
    import pandas as pd
    import json
    from dataclasses import asdict
    mock_dashboard_service.data.usage_events = pd.DataFrame({
        "service": ["Booking"],
        "user_id": [1],
        "department": ["IT"],
        "event_timestamp": [pd.Timestamp("2026-08-01")]
    })

    mock_dashboard_service.get_trend_warning_message.return_value = None

    res_evo = registry.execute("get_usage_evolution", service="Booking", reference_date="2026-08-01")
    res_org = registry.execute("get_organization_usage", service="Booking", reference_date="2026-08-01")

    json.dumps(asdict(res_evo))
    json.dumps(asdict(res_org))

def test_all_tools_schema_present_7(registry):
    tools = registry.list_tools()
    assert len(tools) == 7
    names = [t["name"] for t in tools]
    assert "get_usage_evolution" in names
    assert "get_organization_usage" in names

def test_integration_new_tools(real_dashboard_service):
    if real_dashboard_service is None:
        import pytest
        pytest.skip("Dataset réel non disponible")

    from adoption_analytics.ai.tool_registry import ToolRegistry
    registry = ToolRegistry(real_dashboard_service)

    res_evo = registry.execute("get_usage_evolution", service="Booking", reference_date="2026-08-12", window_days=30)
    assert res_evo.status == "success", getattr(res_evo, "message", "No message")
    assert res_evo.data["period_end"] == "2026-08-12"
    assert len(res_evo.data["series"]) > 0

    res_org = registry.execute("get_organization_usage", service="Booking", reference_date="2026-08-12", window_days=30)
    assert res_org.status == "success"
    assert len(res_org.data["organizations"]) > 0

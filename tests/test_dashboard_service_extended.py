import pandas as pd
import pytest
from adoption_analytics.services.dashboard_service import DashboardService, ServiceExtendedAnalytics
from adoption_analytics.data_sources.registry import DashboardData

@pytest.fixture
def mock_dashboard_service():
    service = DashboardService()
    
    events = pd.DataFrame({
        "event_timestamp": ["2026-08-12 10:00:00", "2026-08-12 11:00:00"],
        "user_id_anonymized": ["u1", "u2"],
        "module": ["HOUSING", "OTHER"],
        "action_name": ["action1", "action2"]
    })
    
    sessions = pd.DataFrame({
        "created_at": ["2026-08-12 10:00:00"],
        "user_id_anonymized": ["u1"]
    })
    
    users = pd.DataFrame({
        "user_id_anonymized": ["u1", "u2"],
        "campus_name": ["Benguerir", "Rabat"]
    })
    
    eligible = pd.DataFrame({
        "service": ["HOUSING", "TRANSPORT", "NEW_MODULE"],
        "campus_name": ["Benguerir", "Rabat", "Benguerir"],
        "eligible_users": [10, 0, 5]
    })
    
    service._data = DashboardData(
        usage_events=pd.DataFrame(),
        web_logs=pd.DataFrame(),
        available_sources=["booking"],
        raw_by_source={
            "booking": {
                "events": events,
                "sessions": sessions,
                "users": users,
                "eligible": eligible
            }
        }
    )
    return service

def test_booking_extended_analytics(mock_dashboard_service):
    # 1. Booking récupère bien les analytics enrichies.
    res = mock_dashboard_service.get_service_extended_analytics("Booking", reference_date=pd.Timestamp("2026-08-12"))
    
    assert res.status == "available"
    
    # 7. les métriques connexion sont exposées
    assert res.connection is not None
    assert res.connection["connected_users_30d"] == 1
    
    # 3. Tous les modules sont retournés
    # 5. TRANSPORT conserve None + eligible_population_unavailable
    modules = res.adoption_by_module
    assert len(modules) == 4
    transport = next(m for m in modules if m["module"] == "TRANSPORT")
    assert transport["status"] == "eligible_population_unavailable"
    assert transport["observed_adoption_rate"] is None
    
    new_module = next(m for m in modules if m["module"] == "NEW_MODULE")
    assert new_module["status"] == "telemetry_unavailable"
    assert new_module["observed_adoption_rate"] is None
    
    # 4. Adoption campus contient plusieurs modules
    campus = res.adoption_by_campus
    assert len(campus) == 3
    
    # 8. les métriques qualité sont exposées
    assert res.data_quality is not None
    assert res.data_quality["event_rows"] == 2
    
def test_unsupported_service_extended_analytics(mock_dashboard_service):
    # 9. un service sans analytics enrichies est géré proprement
    res = mock_dashboard_service.get_service_extended_analytics("Learning Center")
    assert res.status == "not_available"
    assert res.usage is None

def test_global_overview_no_aggregation(mock_dashboard_service):
    # 10. get_global_overview n'agrège toujours pas DAU/WAU/MAU entre services
    usage = pd.DataFrame({
        "service": ["Booking", "Learning Center"],
        "event_timestamp": pd.to_datetime(["2026-08-12", "2026-08-12"]),
        "user_id": ["u1", "u1"]
    })
    res = mock_dashboard_service.get_global_overview(usage, ["Booking", "Learning Center"], kpi_usage=usage)
    assert len(res["table_data"]) == 2
    assert "DAU global" not in res

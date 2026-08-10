import pytest
import pandas as pd
from adoption_analytics.services.dashboard_service import DashboardService

@pytest.fixture
def service():
    return DashboardService()

def test_single_day_warning_for_mono_service(service):
    # Une source avec 1 seul jour produit le warning
    data = {
        "service": ["Ecommerce Demo", "Ecommerce Demo"],
        "event_timestamp": pd.to_datetime(["2023-11-01 10:00:00", "2023-11-01 14:00:00"])
    }
    filtered_usage = pd.DataFrame(data)
    
    warning = service.get_trend_warning_message(filtered_usage, "Ecommerce Demo")
    assert warning is not None
    assert "Historique insuffisant" in warning
    assert "Une seule journée de données" in warning

def test_multiple_days_no_warning_for_mono_service(service):
    data = {
        "service": ["Booking", "Booking"],
        "event_timestamp": pd.to_datetime(["2023-11-01 10:00:00", "2023-11-02 14:00:00"])
    }
    filtered_usage = pd.DataFrame(data)
    
    warning = service.get_trend_warning_message(filtered_usage, "Booking")
    assert warning is None

def test_tous_les_services_heterogeneous_dates(service):
    # Tous les services avec périodes diffèrent produit une note
    data = {
        "service": ["Booking", "Learning Center"],
        "event_timestamp": pd.to_datetime(["2023-11-01 10:00:00", "2023-11-02 14:00:00"])
    }
    filtered_usage = pd.DataFrame(data)
    
    warning = service.get_trend_warning_message(filtered_usage, "Tous les services")
    assert warning is not None
    assert "Les périodes disponibles diffèrent selon les services" in warning
    assert "Une seule journée" not in warning

def test_tous_les_services_homogeneous_dates(service):
    # Même période pour tous les services
    data = {
        "service": ["Booking", "Booking", "Learning Center", "Learning Center"],
        "event_timestamp": pd.to_datetime([
            "2023-11-01 10:00:00", "2023-11-05 10:00:00", 
            "2023-11-01 10:00:00", "2023-11-05 10:00:00"
        ])
    }
    filtered_usage = pd.DataFrame(data)
    
    warning = service.get_trend_warning_message(filtered_usage, "Tous les services")
    assert warning is None

import pytest
import pandas as pd
from adoption_analytics.services.dashboard_service import DashboardService

def test_kpi_history_booking_derniere_date():
    # A. Booking-like dataset :
    # reference_date = 23/07, événements présents sur 30 jours
    # "Dernière date disponible" -> DAU sur le dernier jour, WAU 7 jours, MAU 30 jours
    
    dates = pd.date_range(start="2026-06-20", end="2026-07-23", freq="D")
    df_list = []
    for d in dates:
        df_list.append({
            "service": "Booking",
            "event_timestamp": d,
            "user_id": f"u_{d.day}",
            "action": "view",
            "department": "IT"
        })
    kpi_usage = pd.DataFrame(df_list)
    
    # filtered_usage restreint au dernier jour
    filtered_usage = kpi_usage[kpi_usage["event_timestamp"] == "2026-07-23"].copy()
    
    service = DashboardService()
    service._data = type("FakeData", (), {"usage_events": pd.DataFrame()})()
    
    vm = service.get_adoption_view(filtered_usage, kpi_usage=kpi_usage)
    metrics = vm.metrics
    
    # DAU (dernier jour, 23/07 = u_23) -> 1
    assert metrics["dau"] == 1
    # WAU (7 derniers jours, 17/07 to 23/07 = 7 distinct users) -> 7
    assert metrics["wau"] == 7
    # MAU (30 derniers jours, 24/06 to 23/07 = 30 distinct users) -> 30
    assert metrics["mau"] == 30
    # On vérifie que WAU et MAU ne sont pas réduits au DAU (1)
    assert metrics["wau"] > metrics["dau"]
    assert metrics["mau"] > metrics["wau"]


def test_tous_les_services_derniere_date():
    # B. Tous les services :
    # service A dernière date = 23/07
    # service B dernière date = 17/07
    
    df_list = []
    # Service A (20 au 23/07)
    for d in pd.date_range(start="2026-07-20", end="2026-07-23", freq="D"):
        df_list.append({"service": "A", "event_timestamp": d, "user_id": f"uA_{d.day}", "action": "view", "department": "IT"})
    # Service B (10 au 17/07)
    for d in pd.date_range(start="2026-07-10", end="2026-07-17", freq="D"):
        df_list.append({"service": "B", "event_timestamp": d, "user_id": f"uB_{d.day}", "action": "view", "department": "IT"})
        
    kpi_usage = pd.DataFrame(df_list)
    
    # filtered_usage restreint au dernier jour de chaque service
    filtered_usage = pd.concat([
        kpi_usage[kpi_usage["service"] == "A"].iloc[-1:],
        kpi_usage[kpi_usage["service"] == "B"].iloc[-1:]
    ])
    
    service = DashboardService()
    overview = service.get_global_overview(filtered_usage, ["A", "B"], kpi_usage=kpi_usage)
    
    table = overview["table_data"]
    
    row_A = next(r for r in table if r["Service"] == "A")
    assert row_A["Dernière donnée disponible"] == "23/07/2026"
    assert row_A["DAU"] == 1
    assert row_A["WAU"] == 4 # 4 days
    
    row_B = next(r for r in table if r["Service"] == "B")
    assert row_B["Dernière donnée disponible"] == "17/07/2026"
    assert row_B["DAU"] == 1
    assert row_B["WAU"] == 7 # 7 days ending 17/07

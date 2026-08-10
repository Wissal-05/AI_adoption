import pytest
import pandas as pd
from adoption_analytics.services.dashboard_service import DashboardService

def test_global_overview_no_naive_dau_mau():
    # Créer un DataFrame mock de filtrage usage
    data = {
        "service": ["Booking", "Booking", "Learning Center", "Learning Center"],
        "event_timestamp": pd.to_datetime([
            "2023-11-01 10:00:00",
            "2023-11-01 11:00:00",
            "2023-11-01 12:00:00",
            "2023-11-02 10:00:00"
        ]),
        "user_id": ["u1", "u2", "u1", "u3"],
        "action": ["login", "login", "view", "view"],
        "session_id": ["s1", "s2", "s3", "s4"]
    }
    filtered_usage = pd.DataFrame(data)
    available_services = ["Booking", "Learning Center"]
    
    service = DashboardService()
    
    overview = service.get_global_overview(filtered_usage, available_services)
    
    # 1. B. Tous les services : aucun DAU/WAU/MAU utilisateur global naïf n'est produit
    # Le résultat d'overview contient uniquement des aggrégations sécurisées
    assert "dau" not in overview
    assert "mau" not in overview
    
    assert overview["services_suivis"] == 2
    assert overview["services_avec_donnees"] == 2
    assert overview["volume_observe"] == 4
    
    # Fraicheur
    assert overview["fraicheur"] == "Hétérogène"
    
    # 2. C. tableau par service : chaque service possède sa propre date de référence
    table_data = overview["table_data"]
    assert len(table_data) == 2
    
    booking_row = next(r for r in table_data if r["Service"] == "Booking")
    assert booking_row["Dernière donnée disponible"] == "01/11/2023"
    assert booking_row["DAU"] >= 0
    
    lc_row = next(r for r in table_data if r["Service"] == "Learning Center")
    assert lc_row["Dernière donnée disponible"] == "02/11/2023"
    assert lc_row["DAU"] >= 0

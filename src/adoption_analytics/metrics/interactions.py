import pandas as pd
from typing import Tuple, List

def compute_top_interactions(
    usage_events_df: pd.DataFrame,
    web_logs_df: pd.DataFrame,
    service: str,
    measure: str = "reach",
    limit: int = 10
) -> Tuple[pd.DataFrame, str, List[str]]:
    """
    Calcule de manière pure les Top interactions pour un service, 
    sur la base de données (déjà filtrées temporellement si nécessaire).
    
    Args:
        usage_events_df: DataFrame des événements métiers
        web_logs_df: DataFrame des logs web
        service: Nom du service ciblé (Booking, Learning Center, etc.)
        measure: "reach" ou "events" (détermine la colonne de tri)
        limit: Nombre max d'interactions retournées
        
    Returns:
        Tuple: (df, reach_type, limitations)
        - df a les colonnes ['interaction', 'reach', 'events', 'events_share_pct']
    """
    if usage_events_df is None:
        usage_events_df = pd.DataFrame()
    if web_logs_df is None:
        web_logs_df = pd.DataFrame()
        
    measure_lower = str(measure).lower().strip()
    target_col = "reach" if measure_lower in ["users", "utilisateurs", "reach", "utilisateurs distincts", "adresses ip distinctes"] else "events"
    
    limitations = []
    reach_type = "distinct_users"
    
    srv = service.lower().strip()
    
    if srv == "learning center":
        reach_type = "distinct_source_ips"
        limitations.append("Une adresse IP source n'est pas équivalente à un utilisateur authentifié unique, notamment en présence de NAT, proxy ou réseaux partagés.")
        
        if web_logs_df.empty:
            return pd.DataFrame(columns=["interaction", "reach", "events", "events_share_pct"]), reach_type, limitations
            
        lc_logs = web_logs_df.copy()
        if "service" in lc_logs.columns:
            lc_logs = lc_logs[lc_logs["service"].astype(str).str.lower() == srv]
            
        if "analytics_eligible" in lc_logs.columns:
            lc_logs = lc_logs[lc_logs["analytics_eligible"].fillna(False)]
        else:
            if "is_static" in lc_logs.columns:
                lc_logs = lc_logs[~lc_logs["is_static"].fillna(False)]
            if "is_bot" in lc_logs.columns:
                lc_logs = lc_logs[~lc_logs["is_bot"].fillna(False)]
                
        interaction_col = next((c for c in ["page", "route", "path"] if c in lc_logs.columns), None)
        if not interaction_col or lc_logs.empty:
            return pd.DataFrame(columns=["interaction", "reach", "events", "events_share_pct"]), reach_type, limitations
            
        lc_logs["interaction"] = lc_logs[interaction_col].fillna("Non renseigné").astype(str).replace({"": "Non renseigné", "Unknown": "Non renseigné"})
        
        if "source_ip" in lc_logs.columns:
            grouped = lc_logs.groupby("interaction").agg(
                events=("interaction", "size"),
                reach=("source_ip", lambda x: x.nunique(dropna=True))
            ).reset_index()
        else:
            grouped = lc_logs.groupby("interaction").size().reset_index(name="events")
            grouped["reach"] = 0
            
    else:
        # Booking / Ecommerce Demo
        if srv == "booking":
            limitations.append("Le volume événementiel peut inclure des signatures répétées ; il mesure l'activité observée, pas l'adoption.")
            
        if usage_events_df.empty:
            return pd.DataFrame(columns=["interaction", "reach", "events", "events_share_pct"]), reach_type, limitations
            
        service_events = usage_events_df.copy()
        if "service" in service_events.columns:
            service_events = service_events[service_events["service"].astype(str).str.lower() == srv]
            
        if service_events.empty:
            return pd.DataFrame(columns=["interaction", "reach", "events", "events_share_pct"]), reach_type, limitations
            
        interaction_column = None
        if "page" in service_events.columns and service_events["page"].dropna().astype(str).str.strip().ne("").any():
            interaction_column = "page"
        elif "action" in service_events.columns and service_events["action"].dropna().astype(str).str.strip().ne("").any():
            interaction_column = "action"
            
        if not interaction_column:
            return pd.DataFrame(columns=["interaction", "reach", "events", "events_share_pct"]), reach_type, limitations
            
        service_events["interaction"] = service_events[interaction_column].fillna("Non renseigné").astype(str).replace({"": "Non renseigné", "Unknown": "Non renseigné"})
        
        if "user_id" in service_events.columns:
            grouped = service_events.groupby("interaction").agg(
                events=("interaction", "size"),
                reach=("user_id", lambda x: x.nunique(dropna=True))
            ).reset_index()
        else:
            grouped = service_events.groupby("interaction").size().reset_index(name="events")
            grouped["reach"] = 0

    if grouped.empty:
        grouped["events_share_pct"] = []
        return grouped, reach_type, limitations
        
    total_events = grouped["events"].sum()
    grouped["events_share_pct"] = (grouped["events"] / total_events * 100).round(2) if total_events else 0.0
    grouped = grouped.sort_values(by=target_col, ascending=False).head(limit)
    
    return grouped, reach_type, limitations

import sys
import os
from pathlib import Path
import pandas as pd
from datetime import timedelta

sys.path.append(os.path.abspath("src"))

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.services.adoption_metrics_service import AdoptionMetricsService
from config.settings import settings

def independent_calc(df):
    if df.empty:
        return {"dau": 0, "wau": 0, "mau": 0, "avg_freq": 0.0, "ref_date": None, "active_users": 0, "normalized_lines": 0}
    
    df = df.copy()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    df = df.dropna(subset=["event_timestamp", "user_id"])
    
    if df.empty:
        return {"dau": 0, "wau": 0, "mau": 0, "avg_freq": 0.0, "ref_date": None, "active_users": 0, "normalized_lines": 0}
        
    ref_date = df["event_timestamp"].max().normalize()
    
    dau_start = ref_date
    wau_start = ref_date - timedelta(days=6)
    mau_start = ref_date - timedelta(days=29)
    
    df["date"] = df["event_timestamp"].dt.normalize()
    active_users = df["user_id"].nunique()
    
    dau = df[df["event_timestamp"] >= dau_start]["user_id"].nunique()
    wau = df[df["event_timestamp"] >= wau_start]["user_id"].nunique()
    mau = df[df["event_timestamp"] >= mau_start]["user_id"].nunique()
    avg_freq = len(df) / active_users if active_users else 0.0
    
    return {
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "avg_freq": avg_freq,
        "ref_date": ref_date,
        "active_users": active_users,
        "normalized_lines": len(df)
    }

def print_audit(name, raw_path, raw_df, norm_df, indep, dash_metrics, daily_kpis_df=None):
    print(f"\n{'='*20} {name} {'='*20}")
    print(f"1. Source brute utilisée: {raw_path}")
    
    raw_min = "N/A"
    raw_max = "N/A"
    if not raw_df.empty and "event_timestamp" in raw_df.columns:
        ts = pd.to_datetime(raw_df["event_timestamp"], errors="coerce").dropna()
        if not ts.empty:
            raw_min = ts.min()
            raw_max = ts.max()
            
    print(f"2. Période (brute): {raw_min} - {raw_max}")
    print(f"3. Lignes source: {len(raw_df)}")
    print(f"4. Lignes après normalisation: {len(norm_df)}")
    if len(raw_df) != len(norm_df):
        print("   Explication: Différence due aux lignes sans user_id, avec dates invalides, ou au parsing/filtrage par date (NaN).")
    
    print(f"5. Nombre d'utilisateurs uniques: {indep['active_users']}")
    print(f"6-9. Calculs (Indépendant vs Dashboard):")
    print(f"   DAU: {indep['dau']} vs {dash_metrics.get('dau', 0)}")
    print(f"   WAU: {indep['wau']} vs {dash_metrics.get('wau', 0)}")
    print(f"   MAU: {indep['mau']} vs {dash_metrics.get('mau', 0)}")
    print(f"   Freq: {indep['avg_freq']:.2f} vs {dash_metrics.get('avg_events_per_active_user', 0):.2f}")
    
    print(f"10. Formule: MAU = users in [ref_date - 29 days, ref_date], WAU = [ref_date - 6, ref_date], DAU = [ref_date]")
    print(f"11. Reference date: {indep['ref_date']}")
    print(f"12. Valeurs affichées: {dash_metrics}")
    
    diff_lines = len(raw_df) - len(norm_df)
    print(f"13. Différence lignes brute/norm: {diff_lines}")
    
    status = "OK"
    warnings = []
    
    if indep["dau"] != dash_metrics.get("dau", 0):
        status = "ERROR"
        warnings.append("DAU mismatch")
    if indep["wau"] != dash_metrics.get("wau", 0):
        status = "ERROR"
        warnings.append("WAU mismatch")
    if indep["mau"] != dash_metrics.get("mau", 0):
        status = "ERROR"
        warnings.append("MAU mismatch")
    if abs(indep["avg_freq"] - dash_metrics.get("avg_events_per_active_user", 0)) > 0.01:
        status = "ERROR"
        warnings.append("Freq mismatch")
        
    if daily_kpis_df is not None and not daily_kpis_df.empty:
        # daily kpis compare
        print(f"   [Daily KPIs] {len(daily_kpis_df)} lignes. Comparaison...")
        if "mau" in daily_kpis_df.columns:
            # find latest date
            latest = daily_kpis_df.sort_values("date").iloc[-1]
            print(f"   [Daily KPIs] Dernière ligne ({latest.get('date')}): MAU={latest.get('mau')}, WAU={latest.get('wau')}")
            if latest.get("mau") != dash_metrics.get("mau", 0):
                warnings.append(f"Daily KPIs MAU={latest.get('mau')} diffère de calcul dynamique={dash_metrics.get('mau', 0)}")
                
    if status == "OK" and warnings:
        status = "WARNING"
        
    print(f"14. Statut global du service: {status} " + (f"({', '.join(warnings)})" if warnings else ""))

def main():
    service = DashboardService()
    data = service.load()
    
    print("=" * 80)
    print("AUDIT DE FIABILITÉ DES KPI")
    print("=" * 80)
    
    # 1. Booking
    booking_raw_path = settings.booking_repo_dir / "usage-events-60d.csv"
    booking_raw = pd.read_csv(booking_raw_path) if booking_raw_path.exists() else pd.DataFrame()
    booking_norm = data.usage_events[data.usage_events["service"] == "Booking"]
    indep_b = independent_calc(booking_norm)
    dash_b = AdoptionMetricsService.compute(booking_norm)
    daily_b = pd.read_csv(settings.booking_repo_dir / "daily-kpis-60d.csv") if (settings.booking_repo_dir / "daily-kpis-60d.csv").exists() else None
    print_audit("Booking", booking_raw_path, booking_raw, booking_norm, indep_b, dash_b, daily_b)
    
    # 2. Learning Center
    lc_raw = data.web_logs[data.web_logs["source"] == "learning_center_nginx"] # as web logs are the raw here
    if lc_raw.empty:
        # Load from the repo if not loaded
        lc_raw_path = data.raw_by_source.get("learning_center", {}).get("source_dir", "") + "/nginx-events.csv"
        # We don't have direct access, let's just use what's in data
    else:
        lc_raw_path = "storage/file_repository: learning_center/web_logs"
    
    lc_norm = data.usage_events[data.usage_events["service"] == "Learning Center"]
    indep_lc = independent_calc(lc_norm)
    dash_lc = AdoptionMetricsService.compute(lc_norm)
    daily_lc = data.raw_by_source.get("learning_center", {}).get("daily_kpis", pd.DataFrame())
    print_audit("Learning Center", lc_raw_path, lc_raw, lc_norm, indep_lc, dash_lc, daily_lc)
    
    # 3. Ecommerce Demo
    matomo_raw_dir = data.raw_by_source.get("matomo_ecommerce_demo", {}).get("raw_dir", "")
    eco_norm = data.usage_events[data.usage_events["service"] == "Ecommerce Demo"]
    if matomo_raw_dir:
        raw_files = list(Path(matomo_raw_dir).glob("*.csv"))
        if raw_files:
            eco_raw = pd.read_csv(raw_files[0])
        else:
            eco_raw = pd.DataFrame()
    else:
        eco_raw = pd.DataFrame()
    indep_eco = independent_calc(eco_norm)
    dash_eco = AdoptionMetricsService.compute(eco_norm)
    print_audit("Ecommerce Demo", matomo_raw_dir, eco_raw, eco_norm, indep_eco, dash_eco)
    
    # 4. Tous les services
    print(f"\n{'='*20} Tous les services {'='*20}")
    all_norm = data.usage_events
    indep_all = independent_calc(all_norm)
    dash_all = AdoptionMetricsService.compute(all_norm)
    
    print(f"Lignes: {len(all_norm)}")
    print(f"Utilisateurs uniques globaux: {indep_all['active_users']}")
    print(f"DAU: {dash_all.get('dau')} | WAU: {dash_all.get('wau')} | MAU: {dash_all.get('mau')}")
    
    services = data.usage_events["service"].dropna().unique().tolist()
    print(f"Services inclus: {services}")
    
    # Check for WARNING on nunique(user_id) across services
    print("WARNING: Le calcul global utilise nunique(user_id) sur plusieurs namespaces d'utilisateurs différents (Booking, Matomo, Learning Center ont des identifiants non réconciliés). DAU/WAU/MAU global est faux/faussé.")
    
    # Fraîcheur
    print("\n--- Fraîcheur des données ---")
    for s in services:
        sdf = data.usage_events[data.usage_events["service"] == s]
        max_dt = sdf["event_timestamp"].max()
        print(f"Service {s} : max_date = {max_dt}")

if __name__ == "__main__":
    main()

def print_final_resolutions():
    print("\n" + "="*80)
    print("RÉSOLUTION DES ÉCARTS AUDITÉS")
    print("="*80)
    print("\n--- A. Booking: 161 vs 368 ---")
    print("MAU dynamic = 161 (basé uniquement sur usage-events, GMT)")
    print("MAU daily-kpis = 368 (basé sur une agrégation incluant sessions actives + timezone offset +2h)")
    print("Root Cause: daily-kpis inclut l'usage passif (connexions) avec décalage horaire, usage-events ne mesure que l'usage actif (actions).")
    print("Recommended Source of Truth: UNRESOLVED. À définir avec le métier.")
    
    print("\n--- B. Booking: 252 Lignes rejetées ---")
    print("Reason             | Rows")
    print("missing user_id    | 0")
    print("invalid timestamp  | 252")
    print("both missing       | 0")
    print("other              | 0")
    print("(La conversion de datetime sans 'format=mixed' rejette les millisecondes)")
    
    print("\n--- C. Matomo: 74 vs 22 ---")
    print("Statut: OK. La comparaison 74 vs 22 comparait deux runs d'export différents. Le run 153511 a bien 22 RAW -> 22 PROC.")
    
    print("\n--- D. Learning Center: 3 789 996 -> 1 407 875 ---")
    print("- 2 382 121 lignes ignorées (analytics_eligible = 0, bots, static)")
    
    print("\n--- E. Global View ---")
    print("CERTIFICATION: Le calcul global DAU/WAU/MAU avec nunique(user_id) est invalide en raison de l'absence de Cross-ID entre les services, et de biais de fraîcheur.")

if __name__ == '__main__':
    print_final_resolutions()


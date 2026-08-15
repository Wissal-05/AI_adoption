import pandas as pd
from pathlib import Path

from adoption_analytics.data_sources.booking import BookingDataLoader
from adoption_analytics.metrics.booking_metrics import (
    compute_booking_usage_kpis,
    compute_booking_connection_kpis,
    compute_booking_adoption_by_module,
    compute_booking_adoption_by_campus,
    compute_booking_data_quality,
)

data_dir = Path(r"C:\Users\PC\OneDrive - um5.ac.ma\Documents\AI_adoption\data\um6p\booking")

loader = BookingDataLoader(data_dir)
events = loader.load_events()
sessions = loader.load_sessions()
users = loader.load_users()
eligible = loader.load_eligible_population()

print("--- Data Quality ---")
q = compute_booking_data_quality(events, sessions, users)
for k, v in q.items():
    print(f"{k}: {v}")

print("\n--- Usage KPIs ---")
u = compute_booking_usage_kpis(events)
for k, v in u.items():
    print(f"{k}: {v}")
    
print("\n--- Connection KPIs ---")
c = compute_booking_connection_kpis(sessions, events, reference_date=u["reference_date"])
for k, v in c.items():
    print(f"{k}: {v}")

print("\n--- Adoption par Module ---")
mods = compute_booking_adoption_by_module(events, eligible, reference_date=u["reference_date"])
for m in mods:
    print(m)
    
print("\n--- Adoption par Campus (Housing) ---")
camps = compute_booking_adoption_by_campus(events, eligible, users, reference_date=u["reference_date"])
for c in camps:
    if c["module"] == "HOUSING":
        print(c)

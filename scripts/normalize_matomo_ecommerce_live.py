from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adoption_analytics.data_sources.matomo import load_all_matomo_live_usage_events


RAW_DIR = PROJECT_ROOT / "data" / "raw" / "matomo" / "ecommerce_demo"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "matomo" / "ecommerce_demo"


def main() -> None:
    usage_df = load_all_matomo_live_usage_events(
        RAW_DIR,
        service_name="Ecommerce Demo",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"usage_events_{timestamp}.csv"

    usage_df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Fichier RAW normalisé exporté : {output_path}")
    print(f"Lignes générées : {len(usage_df)}")

    if usage_df.empty:
        print("Aucune donnée RAW normalisée.")
        return

    print(f"Services : {usage_df['service'].unique().tolist()}")
    print(f"Source : {usage_df['source'].unique().tolist()}")
    print(f"Visiteurs Matomo distincts : {usage_df['user_id'].nunique()}")
    print(f"Sessions Matomo distinctes : {usage_df['session_id'].nunique()}")
    print(f"Actions : {usage_df['action'].value_counts().to_dict()}")
    print(f"Pages : {usage_df['page'].nunique()}")


if __name__ == "__main__":
    main()

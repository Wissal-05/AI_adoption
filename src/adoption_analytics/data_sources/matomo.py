from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


COMMON_COLUMNS = [
    "event_timestamp",
    "date",
    "event_date_local",
    "user_id",
    "service",
    "action",
    "page",
    "url",
    "source",
    "session_id",
    "event_type",
    "department",
    "entity",
    "campus",
    "nb_visits",
    "nb_uniq_visitors",
    "nb_hits",
    "sum_time_spent",
    "avg_time_on_page",
    "bounce_rate",
    "exit_rate",
    "normalization_note",
]


def _to_int(value, default: int = 0) -> int:
    """Convertit une valeur Matomo en entier."""

    if pd.isna(value):
        return default

    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    """Convertit une valeur Matomo en nombre décimal."""

    if pd.isna(value):
        return default

    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def classify_matomo_page_action(page: str) -> str:
    """Classe une page Matomo en action métier simple."""

    page = str(page or "").strip().lower()

    if page.startswith("/product/"):
        return "product_view"

    if page.startswith("/checkout"):
        return "checkout_visit"

    if page in {"/signin", "/signup", "/login"}:
        return "auth_visit"

    if page in {"/shop", "/featured", "/recommended"}:
        return "catalog_view"

    return "page_view"


def _load_visits_summary(visits_summary_path: str | Path | None) -> dict:
    """Charge visits_summary_*.json si disponible."""

    if visits_summary_path is None:
        return {}

    path = Path(visits_summary_path)

    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def normalize_matomo_page_urls(
    page_urls_df: pd.DataFrame,
    visits_summary: dict | None = None,
    export_date: str | pd.Timestamp | None = None,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Normalise Actions.getPageUrls vers le modèle commun.

    Attention :
    L'export Matomo Actions.getPageUrls est agrégé par page.
    Il ne contient pas chaque événement individuel.

    Pour rendre les données compatibles avec les KPI du projet,
    chaque nb_hits est transformé en événements page_view synthétiques.
    """

    if page_urls_df.empty:
        return pd.DataFrame(columns=COMMON_COLUMNS)

    visits_summary = visits_summary or {}

    total_unique_visitors = max(
        _to_int(visits_summary.get("nb_uniq_visitors"), default=1),
        1,
    )
    total_visits = max(
        _to_int(visits_summary.get("nb_visits"), default=1),
        1,
    )

    base_timestamp = pd.Timestamp(export_date or pd.Timestamp.now()).normalize()

    rows = []
    global_event_index = 0

    for _, row in page_urls_df.iterrows():
        page = row.get("Actions_PageUrl") or row.get("label") or "/"
        page = str(page).strip() if pd.notna(page) else "/"

        url = row.get("url")
        nb_hits = max(_to_int(row.get("nb_hits"), default=0), 0)
        page_nb_visits = max(_to_int(row.get("nb_visits"), default=0), 0)
        page_nb_uniq_visitors = max(
            _to_int(row.get("nb_uniq_visitors"), default=0),
            0,
        )

        action = classify_matomo_page_action(page)

        for hit_index in range(nb_hits):
            visitor_number = (global_event_index % total_unique_visitors) + 1
            visit_number = (global_event_index % total_visits) + 1
            event_timestamp = base_timestamp + pd.Timedelta(seconds=global_event_index)

            global_event_index += 1

            rows.append(
                {
                    "event_timestamp": event_timestamp,
                    "date": event_timestamp.date().isoformat(),
                    "event_date_local": event_timestamp.date().isoformat(),
                    "user_id": f"matomo_visitor_{visitor_number:03d}",
                    "service": service_name,
                    "action": action,
                    "page": page,
                    "url": url,
                    "source": "matomo",
                    "session_id": f"matomo_visit_{visit_number:03d}",
                    "event_type": "page_view",
                    "department": "Non renseigné",
                    "entity": "Non renseigné",
                    "campus": "Non renseigné",
                    "nb_visits": page_nb_visits,
                    "nb_uniq_visitors": page_nb_uniq_visitors,
                    "nb_hits": nb_hits,
                    "sum_time_spent": _to_float(row.get("sum_time_spent")),
                    "avg_time_on_page": _to_float(row.get("avg_time_on_page")),
                    "bounce_rate": row.get("bounce_rate"),
                    "exit_rate": row.get("exit_rate"),
                    "normalization_note": (
                        "Événement synthétique généré depuis un export Matomo agrégé."
                    ),
                }
            )

    return pd.DataFrame(rows, columns=COMMON_COLUMNS)


def find_latest_file(raw_dir: str | Path, pattern: str) -> Path:
    """Retourne le dernier fichier correspondant au pattern."""

    raw_path = Path(raw_dir)
    candidates = sorted(raw_path.glob(pattern))

    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier trouvé dans {raw_path} avec le pattern {pattern}"
        )

    return candidates[-1]


def extract_export_date_from_filename(filename: str) -> pd.Timestamp | None:
    """Extrait la date depuis un nom comme page_urls_20260805_114421.csv."""

    match = re.search(r"_(\d{8})_", filename)

    if not match:
        return None

    return pd.to_datetime(match.group(1), format="%Y%m%d")


def load_latest_matomo_usage_events(
    raw_dir: str | Path,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Charge les derniers exports Matomo et retourne un DataFrame normalisé."""

    page_urls_file = find_latest_file(raw_dir, "page_urls_*.csv")
    visits_summary_file = find_latest_file(raw_dir, "visits_summary_*.json")

    page_urls_df = pd.read_csv(page_urls_file)
    visits_summary = _load_visits_summary(visits_summary_file)
    export_date = extract_export_date_from_filename(page_urls_file.name)

    return normalize_matomo_page_urls(
        page_urls_df=page_urls_df,
        visits_summary=visits_summary,
        export_date=export_date,
        service_name=service_name,
    )
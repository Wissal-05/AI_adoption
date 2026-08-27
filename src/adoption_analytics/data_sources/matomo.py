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
def find_latest_processed_matomo_usage_export(processed_dir: str | Path) -> Path:
    """Retourne le dernier fichier usage_events_*.csv normalisé."""

    processed_path = Path(processed_dir)
    candidates = sorted(processed_path.glob("usage_events_*.csv"))

    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier usage_events_*.csv trouvé dans {processed_path}"
        )

    return candidates[-1]


def load_latest_processed_matomo_usage_events(
    processed_dir: str | Path,
) -> pd.DataFrame:
    """Charge le dernier fichier Matomo déjà normalisé."""

    latest_file = find_latest_processed_matomo_usage_export(processed_dir)
    usage_df = pd.read_csv(latest_file)

    if "event_timestamp" in usage_df.columns:
        usage_df["event_timestamp"] = pd.to_datetime(
            usage_df["event_timestamp"],
            errors="coerce",
        )

    for column in COMMON_COLUMNS:
        if column not in usage_df.columns:
            if column in {
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
                "bounce_rate",
                "exit_rate",
                "normalization_note",
            }:
                usage_df[column] = "Non renseigné"
            else:
                usage_df[column] = 0

    usage_df = usage_df.dropna(subset=["event_timestamp", "user_id", "service"])

    return usage_df[COMMON_COLUMNS]


def load_matomo_usage_for_dashboard(
    raw_dir: str | Path,
    processed_dir: str | Path,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Charge Matomo pour le dashboard unifié.

    Priorité :
    1. Utiliser le dernier fichier déjà normalisé dans data/processed.
    2. Sinon, normaliser automatiquement depuis data/raw.
    3. Sinon, retourner un DataFrame vide.
    """

    processed_path = Path(processed_dir)
    raw_path = Path(raw_dir)

    try:
        if processed_path.exists() and list(processed_path.glob("usage_events_*.csv")):
            return load_latest_processed_matomo_usage_events(processed_path)
    except FileNotFoundError:
        pass

    try:
        if raw_path.exists() and list(raw_path.glob("page_urls_*.csv")):
            return load_latest_matomo_usage_events(
                raw_path,
                service_name=service_name,
            )
    except FileNotFoundError:
        pass

    return pd.DataFrame(columns=COMMON_COLUMNS)


def _extract_path_from_url(url: str | None) -> str:
    """Extrait le chemin d'une URL Matomo."""

    from urllib.parse import urlparse

    if not url or pd.isna(url):
        return "Non renseigné"

    parsed = urlparse(str(url))
    return parsed.path or "/"


def _parse_live_action_timestamp(
    visit: dict,
    action: dict,
    fallback_timestamp: pd.Timestamp,
) -> pd.Timestamp:
    """Construit un timestamp fiable pour une action RAW Matomo."""

    raw_timestamp = action.get("timestamp")

    if raw_timestamp is not None:
        parsed_timestamp = pd.to_datetime(
            raw_timestamp,
            unit="s",
            errors="coerce",
        )

        if pd.notna(parsed_timestamp):
            return parsed_timestamp

    for candidate in [
        action.get("serverDatePretty"),
        action.get("serverTimePretty"),
        visit.get("lastActionDateTime"),
        visit.get("serverDate"),
    ]:
        if candidate:
            parsed_timestamp = pd.to_datetime(candidate, errors="coerce")

            if pd.notna(parsed_timestamp):
                return parsed_timestamp

    return fallback_timestamp


def normalize_matomo_live_visits(
    live_visits: list[dict],
    export_date: str | pd.Timestamp | None = None,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Normalise Live.getLastVisitsDetails vers le modèle commun.

    Contrairement à Actions.getPageUrls, cette source est détaillée :
    on utilise les actionDetails réels de chaque visite.
    """

    if not live_visits:
        return pd.DataFrame(columns=COMMON_COLUMNS)

    base_timestamp = pd.Timestamp(export_date or pd.Timestamp.now()).normalize()

    rows = []
    global_event_index = 0

    for visit_index, visit in enumerate(live_visits, start=1):
        visitor_id = (
            visit.get("visitorId")
            or visit.get("userId")
            or f"matomo_visitor_{visit_index:03d}"
        )

        visit_id = (
            visit.get("idVisit")
            or visit.get("visitId")
            or f"matomo_visit_{visit_index:03d}"
        )

        action_details = visit.get("actionDetails") or []

        for action_detail in action_details:
            fallback_timestamp = base_timestamp + pd.Timedelta(
                seconds=global_event_index
            )

            event_timestamp = _parse_live_action_timestamp(
                visit=visit,
                action=action_detail,
                fallback_timestamp=fallback_timestamp,
            )

            global_event_index += 1

            url = action_detail.get("url")
            page = _extract_path_from_url(url)
            action = classify_matomo_page_action(page)

            event_type = action_detail.get("type") or "page_view"
            if event_type == "action":
                event_type = "page_view"

            rows.append(
                {
                    "event_timestamp": event_timestamp,
                    "date": event_timestamp.date().isoformat(),
                    "event_date_local": event_timestamp.date().isoformat(),
                    "user_id": f"matomo_visitor_{visitor_id}",
                    "service": service_name,
                    "action": action,
                    "page": page,
                    "url": url,
                    "source": "matomo_live",
                    "session_id": f"matomo_visit_{visit_id}",
                    "event_type": event_type,
                    "department": "Non renseigné",
                    "entity": "Non renseigné",
                    "campus": "Non renseigné",
                    "nb_visits": 1,
                    "nb_uniq_visitors": 1,
                    "nb_hits": 1,
                    "sum_time_spent": _to_float(action_detail.get("timeSpent")),
                    "avg_time_on_page": _to_float(action_detail.get("timeSpent")),
                    "bounce_rate": None,
                    "exit_rate": None,
                    "normalization_note": (
                        "Événement détaillé extrait depuis Live.getLastVisitsDetails."
                    ),
                }
            )

    return pd.DataFrame(rows, columns=COMMON_COLUMNS)


def find_latest_matomo_live_visits_export(raw_dir: str | Path) -> Path:
    """Retourne le dernier fichier live_visits_*.json exporté."""

    raw_path = Path(raw_dir)
    candidates = sorted(raw_path.glob("live_visits_*.json"))

    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier live_visits_*.json trouvé dans {raw_path}"
        )

    return candidates[-1]


def load_latest_matomo_live_usage_events(
    raw_dir: str | Path,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Charge le dernier export RAW Matomo et retourne un usage_df détaillé."""

    latest_file = find_latest_matomo_live_visits_export(raw_dir)

    live_visits = json.loads(
        latest_file.read_text(encoding="utf-8")
    )

    export_date = extract_export_date_from_filename(latest_file.name)

    return normalize_matomo_live_visits(
        live_visits=live_visits,
        export_date=export_date,
        service_name=service_name,
    )


def load_all_matomo_live_usage_events(
    raw_dir: str | Path,
    service_name: str = "Ecommerce Demo",
) -> pd.DataFrame:
    """Charge et consolide tous les exports RAW Matomo live_visits en dédupliquant par idVisit."""
    
    raw_path = Path(raw_dir)
    files = sorted(raw_path.glob("live_visits_*.json"))
    
    if not files:
        raise FileNotFoundError(f"Aucun fichier live_visits_*.json trouvé dans {raw_path}")
        
    consolidated_visits = {}
    
    for file_path in files:
        try:
            visits = json.loads(file_path.read_text(encoding="utf-8"))
            for visit in visits:
                id_visit = visit.get("idVisit")
                if id_visit:
                    consolidated_visits[id_visit] = visit
        except Exception:
            pass
            
    all_visits_list = list(consolidated_visits.values())
    
    export_date = extract_export_date_from_filename(files[-1].name)
    
    return normalize_matomo_live_visits(
        live_visits=all_visits_list,
        export_date=export_date,
        service_name=service_name,
    )
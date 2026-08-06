from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "matomo" / "ecommerce_demo"


def load_env_file() -> None:
    """Charge un fichier .env simple sans dépendance externe."""

    env_path = PROJECT_ROOT / ".env"

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def call_matomo_live_api(count_visitors_to_fetch: int = 100):
    """Appelle l'API Matomo Live.getLastVisitsDetails en POST."""

    base_url = os.environ.get("MATOMO_BASE_URL", "http://localhost:8080").rstrip("/")
    site_id = os.environ.get("MATOMO_SITE_ID", "1")
    token_auth = os.environ.get("MATOMO_TOKEN_AUTH")

    if not token_auth:
        raise RuntimeError(
            "MATOMO_TOKEN_AUTH est manquant. Ajoute-le dans le fichier .env."
        )

    params = {
        "module": "API",
        "method": "Live.getLastVisitsDetails",
        "idSite": site_id,
        "period": "day",
        "date": "today",
        "format": "JSON",
        "token_auth": token_auth,
        "countVisitorsToFetch": str(count_visitors_to_fetch),
        "doNotFetchActions": "0",
        "enhanced": "1",
    }

    body = urllib.parse.urlencode(params).encode("utf-8")
    url = f"{base_url}/index.php"

    request = urllib.request.Request(url, data=body, method="POST")

    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)

    if isinstance(data, dict) and data.get("result") == "error":
        raise RuntimeError(data.get("message", "Erreur API Matomo inconnue."))

    return data


def save_json(filename: str, data) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"JSON RAW exporté : {path}")
    return path


def extract_path(url: str | None) -> str:
    """Extrait le chemin d'une URL."""

    if not url:
        return "Non renseigné"

    parsed = urlparse(str(url))
    return parsed.path or "/"


def flatten_live_actions(visits: list[dict]) -> list[dict]:
    """Transforme les visites RAW Matomo en lignes d'actions lisibles."""

    rows = []

    for visit_index, visit in enumerate(visits, start=1):
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

        for action_index, action in enumerate(action_details, start=1):
            url = action.get("url")
            page = extract_path(url)

            rows.append(
                {
                    "visitor_id": visitor_id,
                    "visit_id": visit_id,
                    "action_index": action_index,
                    "action_type": action.get("type"),
                    "page": page,
                    "url": url,
                    "page_title": action.get("pageTitle") or action.get("title"),
                    "server_time_pretty": action.get("serverTimePretty"),
                    "server_date_pretty": action.get("serverDatePretty"),
                    "timestamp": action.get("timestamp"),
                    "time_spent": action.get("timeSpent"),
                    "device_type": visit.get("deviceType"),
                    "browser": visit.get("browserName"),
                    "operating_system": visit.get("operatingSystemName"),
                    "country": visit.get("country"),
                    "referrer_type": visit.get("referrerType"),
                    "referrer_name": visit.get("referrerName"),
                }
            )

    return rows


def save_live_actions_csv(filename: str, rows: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename

    fieldnames = [
        "visitor_id",
        "visit_id",
        "action_index",
        "action_type",
        "page",
        "url",
        "page_title",
        "server_time_pretty",
        "server_date_pretty",
        "timestamp",
        "time_spent",
        "device_type",
        "browser",
        "operating_system",
        "country",
        "referrer_type",
        "referrer_name",
    ]

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV actions RAW exporté : {path}")
    return path


def main() -> None:
    load_env_file()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    visits = call_matomo_live_api(count_visitors_to_fetch=100)

    if not isinstance(visits, list):
        raise RuntimeError("La réponse Live.getLastVisitsDetails n'est pas une liste.")

    save_json(f"live_visits_{timestamp}.json", visits)

    action_rows = flatten_live_actions(visits)
    save_live_actions_csv(f"live_actions_{timestamp}.csv", action_rows)

    print("Extraction RAW Matomo terminée.")
    print(f"Visites RAW : {len(visits)}")
    print(f"Actions RAW : {len(action_rows)}")


if __name__ == "__main__":
    main()

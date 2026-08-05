from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


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


def call_matomo_api(method: str, extra_params: dict | None = None):
    """Appelle l'API Matomo en POST et retourne la réponse JSON."""

    base_url = os.environ.get("MATOMO_BASE_URL", "http://localhost:8080").rstrip("/")
    site_id = os.environ.get("MATOMO_SITE_ID", "1")
    token_auth = os.environ.get("MATOMO_TOKEN_AUTH")

    if not token_auth:
        raise RuntimeError(
            "MATOMO_TOKEN_AUTH est manquant. Ajoute-le dans le fichier .env."
        )

    params = {
        "module": "API",
        "method": method,
        "idSite": site_id,
        "period": "day",
        "date": "today",
        "format": "JSON",
        "token_auth": token_auth,
    }

    if extra_params:
        params.update(extra_params)

    body = urllib.parse.urlencode(params).encode("utf-8")
    url = f"{base_url}/index.php"

    request = urllib.request.Request(url, data=body, method="POST")

    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)

    if isinstance(data, dict) and data.get("result") == "error":
        raise RuntimeError(data.get("message", "Erreur API Matomo inconnue."))

    return data


def save_json(filename: str, data) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"JSON exporté : {path}")


def save_page_urls_csv(filename: str, rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUTPUT_DIR / filename

    fieldnames = [
        "label",
        "nb_visits",
        "nb_uniq_visitors",
        "nb_hits",
        "sum_time_spent",
        "avg_time_on_page",
        "bounce_rate",
        "exit_rate",
        "entry_nb_visits",
        "exit_nb_visits",
        "url",
        "Actions_PageUrl",
    ]

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "label": row.get("label"),
                    "nb_visits": row.get("nb_visits"),
                    "nb_uniq_visitors": row.get("nb_uniq_visitors"),
                    "nb_hits": row.get("nb_hits"),
                    "sum_time_spent": row.get("sum_time_spent"),
                    "avg_time_on_page": row.get("avg_time_on_page"),
                    "bounce_rate": row.get("bounce_rate"),
                    "exit_rate": row.get("exit_rate"),
                    "entry_nb_visits": row.get("entry_nb_visits"),
                    "exit_nb_visits": row.get("exit_nb_visits"),
                    "url": row.get("url"),
                    "Actions_PageUrl": row.get("Actions_PageUrl"),
                }
            )

    print(f"CSV exporté : {path}")


def main() -> None:
    load_env_file()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    visits_summary = call_matomo_api("VisitsSummary.get")

    page_urls = call_matomo_api(
        "Actions.getPageUrls",
        {
            "flat": "1",
            "filter_limit": "-1",
        },
    )

    page_titles = call_matomo_api(
        "Actions.getPageTitles",
        {
            "flat": "1",
            "filter_limit": "-1",
        },
    )

    save_json(f"visits_summary_{timestamp}.json", visits_summary)
    save_json(f"page_urls_{timestamp}.json", page_urls)
    save_json(f"page_titles_{timestamp}.json", page_titles)

    if isinstance(page_urls, list):
        save_page_urls_csv(f"page_urls_{timestamp}.csv", page_urls)

    print("Extraction Matomo terminée.")


if __name__ == "__main__":
    main()
"""AI Adoption Analytics — Interface Streamlit.

Ce fichier est la couche UI pure. Il ne contient aucune logique métier :
tous les calculs et traitements sont délégués aux services.

Architecture :
  app.py → services/ → metrics/ + reporting/ + ai/ → data_sources/ → schemas/
"""

from pathlib import Path
import sys
import pandas as pd
import altair as alt
import plotly.express as px

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.services.security_service import SecurityService
from adoption_analytics.services.data_freshness import DataFreshnessService
from adoption_analytics.ai import get_assistant
from adoption_analytics.metrics.learning_center import prepare_daily_trend
from adoption_analytics.metrics.adoption import (
    compute_usage_frequency,
    departmental_breakdown,
    compute_advanced_adoption_kpis,
)
from adoption_analytics.ui.filters import (
    PERIOD_OPTIONS,
    apply_date_filter,
    compute_period_change,
    get_available_date_bounds,
    get_previous_window,
    resolve_period,
)
from adoption_analytics.ui.theme import apply_um6p_theme

# ── Configuration de la page ───────────────────────────────────────────────────

st.set_page_config(page_title="AI Adoption Analytics", layout="wide")

apply_um6p_theme()


# ── Chargement des données (mis en cache par session) ─────────────────────────

@st.cache_resource(show_spinner="Chargement des données...")
def load_data():
    service = DashboardService()
    data = service.load()
    return service, data


dashboard_service, data = load_data()

def format_optional_percentage(value: float | None) -> str:
    """Formate un pourcentage optionnel pour l'affichage Streamlit."""

    if value is None:
        return "Non calculable"

    return f"{value:.1f} %"

def build_unified_adoption_trend(
    usage_df: pd.DataFrame,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
    service_bounds: dict[str, tuple[pd.Timestamp, pd.Timestamp]] | None = None
) -> pd.DataFrame:
    """Construit une tendance quotidienne commune DAU / WAU / MAU / événements / fréquence par service."""

    required_columns = {"event_timestamp", "user_id", "service"}
    if usage_df.empty or not required_columns.issubset(usage_df.columns):
        return pd.DataFrame(
            columns=["date", "service", "dau", "wau", "mau", "events", "frequency"]
        )

    df = usage_df.copy()
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    df = df.dropna(subset=["event_timestamp", "user_id", "service"])

    if df.empty:
        return pd.DataFrame(
            columns=["date", "service", "dau", "wau", "mau", "events", "frequency"]
        )

    df["date"] = df["event_timestamp"].dt.normalize()

    rows = []

    for service, service_df in df.groupby("service"):
        service_df = service_df[["date", "user_id"]].copy()

        daily_users = (
            service_df.groupby("date")["user_id"]
            .agg(lambda users: set(users.dropna()))
            .to_dict()
        )

        daily_events = service_df.groupby("date").size().to_dict()

        if service_bounds and service in service_bounds:
            actual_min, actual_max = service_bounds[service]
            if start_date is not None and end_date is not None:
                eff_start = max(actual_min, start_date.normalize())
                eff_end = min(actual_max, end_date.normalize())
                if eff_start <= eff_end:
                    unique_dates = pd.date_range(eff_start, eff_end)
                else:
                    unique_dates = pd.DatetimeIndex([])
            else:
                unique_dates = pd.date_range(actual_min, actual_max)
        else:
            if start_date is not None and end_date is not None:
                unique_dates = pd.date_range(start_date.normalize(), end_date.normalize())
            else:
                unique_dates = pd.date_range(service_df["date"].min(), service_df["date"].max())

        for current_date in unique_dates:
            day_users = daily_users.get(current_date, set())
            day_events = int(daily_events.get(current_date, 0))

            wau_users = set()
            for date in pd.date_range(current_date - pd.Timedelta(days=6), current_date):
                wau_users.update(daily_users.get(date, set()))

            mau_users = set()
            for date in pd.date_range(current_date - pd.Timedelta(days=29), current_date):
                mau_users.update(daily_users.get(date, set()))

            dau = len(day_users)
            frequency = day_events / dau if dau else 0

            rows.append(
                {
                    "date": current_date,
                    "service": service,
                    "dau": dau,
                    "wau": len(wau_users),
                    "mau": len(mau_users),
                    "events": day_events,
                    "frequency": frequency,
                }
            )

    return pd.DataFrame(rows)

def prepare_unified_entity_usage_table(departmental_df: pd.DataFrame) -> pd.DataFrame:
    """Prépare une table commune d'usage par entité/campus pour tous les services."""

    display_columns = [
        "Entité / campus",
        "Service",
        "Utilisateurs actifs",
        "Événements",
        "Événements / utilisateur",
        "Part des utilisateurs actifs (%)",
        "Taux d’utilisation",
        "Statut données",
    ]

    if departmental_df.empty:
        return pd.DataFrame(columns=display_columns)

    data = departmental_df.copy()

    source_columns = {
        "department": "Entité / campus",
        "service": "Service",
        "active_users": "Utilisateurs actifs",
        "events": "Événements",
        "avg_events_per_user": "Événements / utilisateur",
        "share_of_active_users": "Part des utilisateurs actifs (%)",
    }

    for source_column in source_columns:
        if source_column not in data.columns:
            if source_column in {"department", "service"}:
                data[source_column] = "Non renseigné"
            else:
                data[source_column] = 0

    data = data[list(source_columns.keys())].rename(columns=source_columns)

    data["Entité / campus"] = (
        data["Entité / campus"]
        .fillna("Non renseigné")
        .replace({"Unknown": "Non renseigné", "": "Non renseigné"})
    )

    data["Service"] = (
        data["Service"]
        .fillna("Non renseigné")
        .replace({"Unknown": "Non renseigné", "": "Non renseigné"})
    )

    numeric_columns = [
        "Utilisateurs actifs",
        "Événements",
        "Événements / utilisateur",
        "Part des utilisateurs actifs (%)",
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    data["Utilisateurs actifs"] = data["Utilisateurs actifs"].astype(int)
    data["Événements"] = data["Événements"].astype(int)
    data["Événements / utilisateur"] = data["Événements / utilisateur"].round(2)
    data["Part des utilisateurs actifs (%)"] = data[
        "Part des utilisateurs actifs (%)"
    ].round(2)

    data["Taux d’utilisation"] = "Non calculable"

    data["Statut données"] = data["Entité / campus"].apply(
        lambda entity: (
            "Mapping entité/campus manquant"
            if entity == "Non renseigné"
            else "Population éligible manquante"
        )
    )

    data = data.sort_values(
        by=["Service", "Utilisateurs actifs"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return data[display_columns]

def classify_interaction_type(
    service: str,
    interaction: str,
    action: str | None = None,
) -> str:
    """Classe une interaction dans une catégorie commune."""

    service_text = str(service).lower()
    interaction_text = str(interaction).lower()
    action_text = str(action or "").lower()

    if "booking" in service_text:
        return "Action métier"

    if "ecommerce" in service_text or "matomo" in service_text:
        if interaction_text.startswith("/product/") or action_text == "product_view":
            return "Vue produit"

        if interaction_text.startswith("/checkout") or action_text == "checkout_visit":
            return "Tunnel checkout"

        if interaction_text in {"/signin", "/signup", "/login"} or action_text == "auth_visit":
            return "Authentification"

        if action_text == "catalog_view":
            return "Catalogue"

        return "Page web"

    if interaction_text.startswith("/api") or "/api/" in interaction_text:
        return "API"

    if interaction_text.startswith("/") or interaction_text.startswith("http"):
        return "Page / route"

    return "Événement d’usage"


def prepare_unified_top_interactions_table(
    usage_df: pd.DataFrame,
    web_logs_df: pd.DataFrame | None = None,
    top_n: int = 15,
) -> pd.DataFrame:
    """Prépare une table commune des interactions les plus fréquentes."""

    display_columns = [
        "Service",
        "Type d’interaction",
        "Interaction",
        "Événements",
        "Part des événements (%)",
        "Statut données",
    ]

    rows = []

    if usage_df.empty or "service" not in usage_df.columns:
        return pd.DataFrame(columns=display_columns)

    services_in_scope = set(
        usage_df["service"].dropna().astype(str).unique().tolist()
    )

    # Services normalisés : Booking, Ecommerce Demo, futures sources usage
    usage_services = sorted(
        usage_df["service"].dropna().astype(str).unique().tolist()
    )

    for service in usage_services:
        # Learning Center est traité avec les vrais web logs plus bas.
        if service.lower() == "learning center":
            continue

        service_events = usage_df[
            usage_df["service"].astype(str).str.lower().eq(service.lower())
        ].copy()

        if service_events.empty:
            continue

        interaction_column = None

        # Pour Matomo / Ecommerce Demo, la page est plus informative que l'action.
        if (
            "page" in service_events.columns
            and service_events["page"].dropna().astype(str).str.strip().ne("").any()
        ):
            interaction_column = "page"
        elif (
            "action" in service_events.columns
            and service_events["action"].dropna().astype(str).str.strip().ne("").any()
        ):
            interaction_column = "action"

        if interaction_column is None:
            continue

        service_events["interaction"] = (
            service_events[interaction_column]
            .fillna("Non renseigné")
            .astype(str)
            .replace({"": "Non renseigné", "Unknown": "Non renseigné"})
        )

        if "action" not in service_events.columns:
            service_events["action"] = None

        service_events["interaction_type"] = service_events.apply(
            lambda row: classify_interaction_type(
                service,
                row["interaction"],
                row.get("action"),
            ),
            axis=1,
        )

        grouped = (
            service_events.groupby(["interaction", "interaction_type"])
            .size()
            .reset_index(name="events")
        )

        total_events = grouped["events"].sum()

        for _, row in grouped.iterrows():
            interaction = row["interaction"]
            interaction_type = row["interaction_type"]
            events = int(row["events"])

            rows.append(
                {
                    "Service": service,
                    "Type d’interaction": interaction_type,
                    "Interaction": interaction,
                    "Événements": events,
                    "Part des événements (%)": round(
                        events / total_events * 100,
                        2,
                    )
                    if total_events
                    else 0,
                    "Statut données": (
                        "Interaction non renseignée"
                        if interaction == "Non renseigné"
                        else "Disponible"
                    ),
                }
            )

    # Learning Center : vraies pages/routes depuis les logs web
    if (
        "Learning Center" in services_in_scope
        and web_logs_df is not None
        and not web_logs_df.empty
    ):
        lc_logs = web_logs_df.copy()

        if "service" in lc_logs.columns:
            lc_logs = lc_logs[
                lc_logs["service"].astype(str).str.lower().eq("learning center")
            ]

        if "analytics_eligible" in lc_logs.columns:
            lc_logs = lc_logs[lc_logs["analytics_eligible"].fillna(False)]
        else:
            if "is_static" in lc_logs.columns:
                lc_logs = lc_logs[~lc_logs["is_static"].fillna(False)]
            if "is_bot" in lc_logs.columns:
                lc_logs = lc_logs[~lc_logs["is_bot"].fillna(False)]

        interaction_column = None

        for candidate_column in ["page", "route", "path"]:
            if candidate_column in lc_logs.columns:
                interaction_column = candidate_column
                break

        if interaction_column is not None and not lc_logs.empty:
            lc_logs["interaction"] = (
                lc_logs[interaction_column]
                .fillna("Non renseigné")
                .astype(str)
                .replace({"": "Non renseigné", "Unknown": "Non renseigné"})
            )

            lc_grouped = (
                lc_logs.groupby("interaction")
                .size()
                .reset_index(name="events")
            )

            lc_total = lc_grouped["events"].sum()

            for _, row in lc_grouped.iterrows():
                interaction = row["interaction"]
                events = int(row["events"])

                rows.append(
                    {
                        "Service": "Learning Center",
                        "Type d’interaction": classify_interaction_type(
                            "Learning Center",
                            interaction,
                        ),
                        "Interaction": interaction,
                        "Événements": events,
                        "Part des événements (%)": round(
                            events / lc_total * 100,
                            2,
                        )
                        if lc_total
                        else 0,
                        "Statut données": (
                            "Interaction non renseignée"
                            if interaction == "Non renseigné"
                            else "Disponible"
                        ),
                    }
                )

    if not rows:
        return pd.DataFrame(columns=display_columns)

    result = pd.DataFrame(rows)

    result = result.sort_values(
        by="Événements",
        ascending=False,
    ).head(top_n)

    return result[display_columns].reset_index(drop=True)

def prepare_unified_data_quality_table(
    usage_df: pd.DataFrame,
    departmental_df: pd.DataFrame,
    web_logs_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Prépare une table de qualité des données par service."""

    display_columns = [
        "Service",
        "Événements disponibles",
        "Utilisateurs actifs observés",
        "Entité / campus",
        "Population éligible",
        "Taux d’utilisation",
        "Interactions",
        "Statut global",
        "Action recommandée",
    ]

    if usage_df.empty or "service" not in usage_df.columns:
        return pd.DataFrame(columns=display_columns)

    services = sorted(usage_df["service"].dropna().astype(str).unique().tolist())
    rows = []

    for service in services:
        service_usage = usage_df[
            usage_df["service"].astype(str).str.lower() == service.lower()
        ].copy()

        events_count = len(service_usage)

        if "user_id" in service_usage.columns:
            active_users = service_usage["user_id"].dropna().nunique()
        else:
            active_users = 0

        # Statut entité / campus
        entity_status = "Non disponible"

        if not departmental_df.empty and "service" in departmental_df.columns:
            service_departmental = departmental_df[
                departmental_df["service"].astype(str).str.lower() == service.lower()
            ].copy()

            if not service_departmental.empty and "department" in service_departmental.columns:
                entities = (
                    service_departmental["department"]
                    .fillna("Non renseigné")
                    .replace({"Unknown": "Non renseigné", "": "Non renseigné"})
                    .astype(str)
                    .unique()
                    .tolist()
                )

                meaningful_entities = [
                    entity for entity in entities if entity != "Non renseigné"
                ]

                if meaningful_entities:
                    entity_status = "Disponible"
                else:
                    entity_status = "Mapping manquant"

        # Statut interactions
        interactions_status = "Non disponible"

        if service.lower() == "learning center":
            if (
                web_logs_df is not None
                and not web_logs_df.empty
                and any(column in web_logs_df.columns for column in ["page", "route", "path"])
            ):
                interactions_status = "Pages / routes disponibles"
        else:
            service_lower = service.lower()

            if "ecommerce" in service_lower or "matomo" in service_lower:
                if "page" in service_usage.columns:
                    available_pages = (
                        service_usage["page"]
                        .dropna()
                        .astype(str)
                        .replace({"": "Non renseigné", "Unknown": "Non renseigné"})
                    )
                    if not available_pages.empty:
                        service_sources = get_source_values(service_usage)
                        has_live_matomo = "matomo_live" in service_sources
                        has_any_matomo = any(
                            source.startswith("matomo") for source in service_sources
                        )

                        if has_live_matomo:
                            interactions_status = "Parcours Matomo Live disponibles"
                        elif has_any_matomo:
                            interactions_status = "Pages Matomo disponibles"

            elif "action" in service_usage.columns:
                available_actions = (
                    service_usage["action"]
                    .dropna()
                    .astype(str)
                    .replace({"": "Non renseigné", "Unknown": "Non renseigné"})
                )
                if not available_actions.empty:
                    interactions_status = "Actions disponibles"
        # Statut global
        missing_items = []

        if entity_status != "Disponible":
            missing_items.append("mapping entité/campus")

        missing_items.append("population éligible")

        if interactions_status == "Non disponible":
            missing_items.append("interactions")

        if len(missing_items) == 1 and missing_items[0] == "population éligible":
            global_status = "Partiel"
        else:
            global_status = "À compléter"

        if not missing_items:
            action_recommandee = "Aucune action prioritaire"
        elif missing_items == ["population éligible"]:
            action_recommandee = "Collecter population éligible"
        else:
            action_recommandee = "Collecter " + " + ".join(missing_items)

        rows.append(
            {
                "Service": service,
                "Événements disponibles": int(events_count),
                "Utilisateurs actifs observés": int(active_users),
                "Entité / campus": entity_status,
                "Population éligible": "Manquante",
                "Taux d’utilisation": "Non calculable",
                "Interactions": interactions_status,
                "Statut global": global_status,
                "Action recommandée": action_recommandee,
            }
        )

    return pd.DataFrame(rows)[display_columns]

def prepare_kpi_interpretation(
    metrics: dict,
    usage_df: pd.DataFrame,
    is_booking: bool = False,
) -> dict:
    """Génère une interprétation contrôlée des KPI communs."""

    dau = int(metrics.get("dau", 0))
    wau = int(metrics.get("wau", 0))
    mau = int(metrics.get("mau", 0))
    frequency = float(metrics.get("avg_events_per_active_user", 0))

    services = []

    if not usage_df.empty and "service" in usage_df.columns:
        services = sorted(
            usage_df["service"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    if len(services) == 0:
        service_scope = "aucun service disponible avec les filtres actuels"
    elif len(services) == 1:
        service_scope = f"le service {services[0]}"
    else:
        service_scope = f"{len(services)} services : {', '.join(services)}"

    if is_booking:
        avg_days = metrics.get("avg_active_days_per_active_user_30d")
        if avg_days is not None:
            freq_str = f"{avg_days}".replace(".", ",")
            observation_freq = f"avec en moyenne {freq_str} jours actifs par utilisateur actif sur les 30 derniers jours."
        else:
            observation_freq = "avec une fréquence d'usage non disponible."
    else:
        observation_freq = f"et une fréquence moyenne de {frequency:.1f} événements par utilisateur actif."

    observation = (
        f"Les KPI affichés couvrent {service_scope}. "
        f"Ils indiquent {dau:,} utilisateurs actifs quotidiens, "
        f"{wau:,} utilisateurs actifs hebdomadaires, "
        f"{mau:,} utilisateurs actifs mensuels, "
        f"{observation_freq}"
    )

    if mau == 0:
        interpretation = (
            "Aucun utilisateur actif mensuel n’est observé avec les filtres actuels. "
            "Cela peut venir d’une période sans activité, d’un filtre trop restrictif "
            "ou d’une indisponibilité des données."
        )
    elif dau > 0 and dau / mau < 0.05:
        interpretation = (
            "L’écart entre le DAU et le MAU indique que l’audience mensuelle est "
            "beaucoup plus large que l’activité quotidienne. Cela peut refléter un usage "
            "non quotidien, ponctuel ou dépendant du type de service analysé."
        )
    elif frequency > 100:
        interpretation = (
            "La fréquence moyenne est élevée, ce qui indique une forte intensité d’usage "
            "par utilisateur actif. Cette intensité peut être positive, mais elle doit être "
            "analysée avec prudence pour vérifier si elle est répartie entre plusieurs "
            "utilisateurs ou concentrée sur quelques profils."
        )
    else:
        interpretation = (
            "Les KPI donnent une première lecture de l’usage observé. Ils permettent de "
            "suivre l’activité, mais ne suffisent pas seuls à conclure sur le taux réel "
            "d’adoption."
        )

    recommendation = (
        "Comparer ces KPI avec la population éligible par service afin de calculer "
        "un vrai taux d’utilisation. Il est aussi recommandé d’analyser les résultats "
        "par service, entité et période pour éviter les conclusions globales trop rapides."
    )

    return {
        "observation": observation,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }

def render_interpretation_popover(insight: dict) -> None:
    """Affiche une interprétation structurée dans un popover."""

    st.caption(
        "Interprétation générée à partir des KPI calculés et des données disponibles."
    )

    st.markdown("**Observation**")
    st.write(insight["observation"])

    st.markdown("**Interprétation**")
    st.write(insight["interpretation"])

    if "recommendation" in insight:
        st.markdown("**Recommandation**")
        st.write(insight["recommendation"])

    recommendations = insight.get("recommendations", [])
    if recommendations:
        st.markdown("**Recommandations**")
        render_recommendations(recommendations)

def prepare_advanced_kpis_interpretation(
    advanced_kpis: dict,
    metrics: dict,
) -> dict:
    """Prépare une interprétation des KPI avancés d'adoption."""

    stickiness = advanced_kpis.get("stickiness_dau_mau")
    weekly_recurrence = advanced_kpis.get("weekly_recurrence_wau_mau")

    if stickiness is None or weekly_recurrence is None:
        return {
            "observation": (
                "Les indicateurs avancés de récurrence ne sont pas calculables "
                "avec les données actuellement disponibles."
            ),
            "interpretation": (
                "Le calcul nécessite au minimum les KPI DAU, WAU et MAU. "
                "Si le MAU est nul ou absent, les ratios DAU/MAU et WAU/MAU "
                "ne peuvent pas être interprétés correctement."
            ),
            "recommendation": (
                "Vérifier la disponibilité des KPI de base et la qualité des "
                "données d'activité avant d'analyser la récurrence d'usage."
            ),
        }

    dau = metrics.get("dau", 0)
    wau = metrics.get("wau", 0)
    mau = metrics.get("mau", 0)

    if stickiness < 5:
        stickiness_level = "faible"
        stickiness_interpretation = (
            "Une faible part des utilisateurs mensuels revient quotidiennement. "
            "L'usage semble donc ponctuel ou concentré sur certains besoins."
        )
    elif stickiness < 20:
        stickiness_level = "modérée"
        stickiness_interpretation = (
            "Une part limitée mais significative des utilisateurs mensuels revient "
            "quotidiennement. L'usage montre une certaine régularité."
        )
    else:
        stickiness_level = "élevée"
        stickiness_interpretation = (
            "Une part importante des utilisateurs mensuels revient quotidiennement. "
            "Le service semble fortement intégré aux usages réguliers."
        )

    if weekly_recurrence < 20:
        recurrence_level = "faible"
    elif weekly_recurrence < 60:
        recurrence_level = "modérée"
    else:
        recurrence_level = "élevée"

    return {
        "observation": (
            f"Les KPI observés sont DAU={dau}, WAU={wau}, MAU={mau}. "
            f"Le stickiness DAU/MAU est de {stickiness:.1f} % et la "
            f"récurrence WAU/MAU est de {weekly_recurrence:.1f} %."
        ),
        "interpretation": (
            f"La récurrence quotidienne est {stickiness_level}. "
            f"La récurrence hebdomadaire est {recurrence_level}. "
            f"{stickiness_interpretation}"
        ),
        "recommendation": (
            "Comparer ces ratios entre services et suivre leur évolution dans le temps. "
            "Pour conclure sur l'adoption réelle, il reste nécessaire de disposer de la "
            "population éligible par service."
        ),
    }

def get_source_values(data: pd.DataFrame) -> set[str]:
    """Retourne les valeurs de source disponibles dans un dataframe."""

    if data.empty or "source" not in data.columns:
        return set()

    return set(
        data["source"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
    )


def has_matomo_live_source(data: pd.DataFrame) -> bool:
    """Indique si le dataframe contient des données détaillées Matomo Live."""

    return "matomo_live" in get_source_values(data)


def has_matomo_source(data: pd.DataFrame) -> bool:
    """Indique si le dataframe contient des données provenant de Matomo."""

    sources = get_source_values(data)

    return any(source.startswith("matomo") for source in sources)


def prepare_matomo_live_journey_preview(
    ecommerce_usage: pd.DataFrame,
    max_rows: int = 10,
) -> pd.DataFrame:
    """Prépare un aperçu lisible des parcours visiteurs Matomo Live."""

    required_columns = {"source", "user_id", "session_id", "action", "page"}

    if ecommerce_usage.empty or not required_columns.issubset(ecommerce_usage.columns):
        return pd.DataFrame()

    live_events = ecommerce_usage[
        ecommerce_usage["source"]
        .fillna("")
        .astype(str)
        .str.lower()
        .eq("matomo_live")
    ].copy()

    if live_events.empty:
        return pd.DataFrame()

    if "event_timestamp" in live_events.columns:
        live_events["event_timestamp"] = pd.to_datetime(
            live_events["event_timestamp"],
            errors="coerce",
        )
        live_events = live_events.sort_values(
            ["session_id", "event_timestamp"],
            na_position="last",
        )
    else:
        live_events = live_events.sort_values(["session_id"])

    rows = []

    for (user_id, session_id), session_events in live_events.groupby(
        ["user_id", "session_id"],
        dropna=False,
    ):
        pages = (
            session_events["page"]
            .fillna("Non renseigné")
            .astype(str)
            .replace({"": "Non renseigné"})
            .tolist()
        )

        actions = (
            session_events["action"]
            .fillna("Non renseigné")
            .astype(str)
            .replace({"": "Non renseigné"})
            .tolist()
        )

        row = {
            "Utilisateur": user_id,
            "Session": session_id,
            "Nb actions": len(session_events),
            "Pages distinctes": session_events["page"].nunique(),
            "Parcours pages": "  ".join(pages[:6]),
            "Actions": "  ".join(actions[:6]),
        }

        if "event_timestamp" in session_events.columns:
            start_time = session_events["event_timestamp"].min()
            end_time = session_events["event_timestamp"].max()

            row["Début"] = (
                start_time.strftime("%Y-%m-%d %H:%M:%S")
                if pd.notna(start_time)
                else "Non renseigné"
            )
            row["Fin"] = (
                end_time.strftime("%Y-%m-%d %H:%M:%S")
                if pd.notna(end_time)
                else "Non renseigné"
            )

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    journey_df = pd.DataFrame(rows)

    return (
        journey_df
        .sort_values("Nb actions", ascending=False)
        .head(max_rows)
        .reset_index(drop=True)
    )


# ── RECOMMANDATIONS HELPERS ─────────────────────────────────────────────

def build_recommendation_section(
    title: str,
    recommendations: list[str],
) -> dict:
    """Construit une section standardisée de recommandations."""

    cleaned_recommendations = [
        recommendation.strip()
        for recommendation in recommendations
        if isinstance(recommendation, str) and recommendation.strip()
    ]

    return {
        "title": title,
        "recommendations": cleaned_recommendations,
    }

def render_recommendations(recommendations: list[str]) -> None:
    """Affiche une liste de recommandations dans un popover ou un conteneur."""

    if not recommendations:
        st.info("Aucune recommandation spécifique générée pour ce bloc.")
        return

    for recommendation in recommendations:
        st.markdown(f"- {recommendation}")

def add_recommendations_to_insight(
    insight: dict,
    recommendations: list[str],
) -> dict:
    """Ajoute des recommandations à un dictionnaire d'interprétation existant."""

    if insight is None:
        insight = {}

    enriched_insight = dict(insight)
    enriched_insight["recommendations"] = [
        recommendation
        for recommendation in recommendations
        if isinstance(recommendation, str) and recommendation.strip()
    ]

    return enriched_insight

def prepare_kpi_recommendations(metrics: dict) -> list[str]:
    """Génère des recommandations opérationnelles à partir des KPI globaux."""

    recommendations = []

    dau = metrics.get("dau")
    wau = metrics.get("wau")
    mau = metrics.get("mau")
    frequency = metrics.get("avg_events_per_active_user")

    if dau is not None and mau:
        try:
            stickiness = float(dau) / float(mau) * 100
            if stickiness < 5:
                recommendations.append(
                    "Surveiller la récurrence d'usage : le rapport DAU/MAU semble faible, "
                    "ce qui peut indiquer un usage occasionnel plutôt qu'une adoption régulière."
                )
            else:
                recommendations.append(
                    "Maintenir le suivi de la récurrence : le niveau d'activité quotidienne "
                    "par rapport au mensuel permet d'évaluer l'engagement réel."
                )
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    if frequency is not None:
        try:
            frequency_value = float(frequency)
            if frequency_value > 500:
                recommendations.append(
                    "Analyser les profils ou services à très forte fréquence afin de vérifier "
                    "s'il s'agit d'un usage métier normal, d'un processus automatisé ou d'un comportement atypique."
                )
            elif frequency_value < 5:
                recommendations.append(
                    "Identifier les freins d'usage possibles : faible fréquence, faible visibilité du service, "
                    "besoin de formation ou parcours utilisateur trop complexe."
                )
        except (TypeError, ValueError):
            pass

    recommendations.append(
        "Compléter la population éligible par service pour transformer les utilisateurs actifs "
        "en vrai taux d'adoption."
    )

    return recommendations

def prepare_advanced_kpi_recommendations(
    advanced_kpis: dict,
) -> list[str]:
    """Génère des recommandations pour stickiness et WAU/MAU."""

    recommendations = []

    stickiness = advanced_kpis.get("stickiness_dau_mau")
    weekly_recurrence = advanced_kpis.get("weekly_recurrence_wau_mau")

    if stickiness is not None:
        try:
            stickiness_value = float(stickiness)
            if stickiness_value < 5:
                recommendations.append(
                    "Mettre en place des actions d'activation ou de rappel pour augmenter "
                    "l'usage quotidien du service."
                )
            elif stickiness_value < 20:
                recommendations.append(
                    "Analyser les segments d'utilisateurs les plus réguliers afin d'identifier "
                    "les bonnes pratiques à généraliser."
                )
            else:
                recommendations.append(
                    "Conserver le suivi du stickiness pour détecter rapidement une baisse "
                    "d'engagement quotidien."
                )
        except (TypeError, ValueError):
            pass

    if weekly_recurrence is not None:
        try:
            recurrence_value = float(weekly_recurrence)
            if recurrence_value < 20:
                recommendations.append(
                    "Renforcer l'accompagnement utilisateur : une faible récurrence hebdomadaire "
                    "peut indiquer que le service n'est pas encore intégré dans les habitudes."
                )
            else:
                recommendations.append(
                    "Exploiter la récurrence hebdomadaire comme indicateur de fidélisation "
                    "et suivre son évolution dans le temps."
                )
        except (TypeError, ValueError):
            pass

    recommendations.append(
        "Comparer ces ratios uniquement entre services ayant une logique d'usage comparable."
    )

    return recommendations

def prepare_evolution_recommendations(
    evolution_data: pd.DataFrame,
    selected_metric: str | None = None,
    selected_service: str | None = None,
) -> list[str]:
    """Génère des recommandations à partir de l'évolution temporelle."""

    recommendations = []

    context = ""
    if selected_service and selected_service != "Tous les services":
        context = f" pour {selected_service}"

    if evolution_data is None or evolution_data.empty:
        return [
            "Collecter un historique plus long afin d'analyser les tendances, les ruptures "
            "et les variations saisonnières."
        ]

    recommendations.append(
        f"Surveiller les ruptures de tendance{context} afin d'identifier rapidement "
        "une baisse d'usage, un incident ou un changement de comportement utilisateur."
    )

    recommendations.append(
        "Corréler les pics et baisses d'activité avec le calendrier métier, les incidents, "
        "les mises en production ou les campagnes de communication."
    )

    if selected_metric:
        recommendations.append(
            f"Analyser la métrique {selected_metric} séparément pour éviter de mélanger "
            "des indicateurs qui ne mesurent pas le même comportement."
        )

    return recommendations

def prepare_entity_usage_recommendations(
    entity_usage_table: pd.DataFrame,
) -> list[str]:
    """Génère des recommandations pour l'usage par entité/campus."""

    recommendations = []

    if entity_usage_table is None or entity_usage_table.empty:
        return [
            "Compléter le mapping utilisateur vers entité, campus ou direction afin "
            "de permettre une analyse organisationnelle fiable."
        ]

    table_text = entity_usage_table.astype(str).to_string().lower()

    if "non renseigné" in table_text or "mapping" in table_text or "manquant" in table_text:
        recommendations.append(
            "Prioriser la récupération du mapping utilisateur vers entité/campus/direction "
            "pour éviter une analyse limitée à 'Non renseigné'."
        )

    recommendations.append(
        "Comparer les campus ou entités uniquement lorsque le mapping est disponible "
        "et que les populations éligibles sont connues."
    )

    recommendations.append(
        "Identifier les entités à faible usage afin de proposer un accompagnement ciblé, "
        "une communication ou une formation."
    )

    recommendations.append(
        "Pour les entités à usage très élevé, vérifier si l'activité correspond à un besoin métier "
        "normal ou à un comportement atypique."
    )

    return recommendations

def prepare_top_interactions_recommendations(
    top_interactions_table: pd.DataFrame,
) -> list[str]:
    """Génère des recommandations pour les pages/actions les plus utilisées."""

    recommendations = []

    if top_interactions_table is None or top_interactions_table.empty:
        return [
            "Définir un dictionnaire des actions métier afin d'interpréter correctement "
            "les interactions les plus fréquentes."
        ]

    table_text = top_interactions_table.astype(str).to_string().lower()

    if "checkout" in table_text or "tunnel" in table_text:
        recommendations.append(
            "Analyser le tunnel checkout : les passages fréquents sur ces pages peuvent révéler "
            "un parcours critique à optimiser."
        )

    if "signin" in table_text or "authentification" in table_text or "auth" in table_text or "login" in table_text:
        recommendations.append(
            "Vérifier le parcours d'authentification : une forte présence des pages de connexion "
            "peut indiquer un point d'entrée important ou un potentiel frottement utilisateur."
        )

    if "product" in table_text or "vue produit" in table_text:
        recommendations.append(
            "Identifier les pages produit les plus consultées et vérifier si elles conduisent "
            "à des actions de conversion ou à une navigation utile."
        )

    recommendations.append(
        "Associer chaque interaction à une signification métier : consultation, recherche, création, "
        "mise à jour, validation ou abandon."
    )

    recommendations.append(
        "Optimiser en priorité les pages ou actions les plus fréquentes, car leur amélioration "
        "aura l'impact le plus visible sur l'expérience utilisateur."
    )

    return recommendations

def prepare_data_quality_recommendations(
    data_quality_table: pd.DataFrame,
) -> list[str]:
    """Génère des recommandations à partir de la qualité des données."""

    recommendations = []

    if data_quality_table is None or data_quality_table.empty:
        return [
            "Mettre en place une matrice de disponibilité des données par service "
            "pour suivre les champs manquants."
        ]

    table_text = data_quality_table.astype(str).to_string().lower()

    if "population" in table_text or "non calculable" in table_text or "manquante" in table_text:
        recommendations.append(
            "Collecter la population éligible par service afin de calculer un vrai taux "
            "d'utilisation/adoption."
        )

    if "mapping" in table_text or "non renseigné" in table_text or "manquant" in table_text:
        recommendations.append(
            "Compléter le mapping utilisateur vers entité/campus/direction pour permettre "
            "l'analyse organisationnelle."
        )

    if "seuil" in table_text or "à compléter" in table_text:
        recommendations.append(
            "Définir des seuils métier pour qualifier l'adoption : faible, moyenne, bonne ou critique."
        )

    recommendations.append(
        "Documenter clairement les champs disponibles, manquants et non calculables pour chaque service."
    )

    recommendations.append(
        "Ne pas remplacer les données manquantes par des valeurs fictives dans le dashboard réel ; "
        "afficher 'Non renseigné' ou 'Non calculable'."
    )

    return recommendations

# ── Sidebar — Navigation ──────────────────────────────────────────────────────
logo_path = ROOT / "assets" / "um6p_logo.png"
if logo_path.exists():
    st.sidebar.image(str(logo_path), use_container_width=True)

st.sidebar.markdown(
    '<div class="um6p-eyebrow" style="margin-bottom: 1.5rem;">ADOPTION ANALYTICS</div>',
    unsafe_allow_html=True,
)

selected_tab = st.sidebar.radio(
    "Navigation",
    options=[
        "Vue d'ensemble",
        "Security Analytics",
        "Assistant IA"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
if st.sidebar.button("Rafraîchir les données", use_container_width=True):
    load_data.clear()
    st.rerun()

filter_opts = dashboard_service.get_filter_options(data.usage_events)

available_services = sorted(
    data.usage_events["service"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

# ── En-tête Principal ──────────────────────────────────────────────────────────
st.markdown('<div class="um6p-eyebrow" style="margin-top: 1.5rem;">ADOPTION ANALYTICS UM6P</div>', unsafe_allow_html=True)
st.title(selected_tab)

if selected_tab == "Vue d'ensemble":
    st.caption("Comprendre l'adoption. Identifier ce qui compte. Agir avec confiance.")
elif selected_tab == "Learning Center":
    st.caption("Analyse détaillée de l'adoption du Learning Center.")
elif selected_tab == "Adoption détaillée":
    st.caption("Vue granulaire de l'utilisation par département et profil.")
elif selected_tab == "Security Analytics":
    st.caption("Surveillance et détection d'activités suspectes.")
elif selected_tab == "Booking":
    st.caption("Analyse des réservations et de l'utilisation des espaces.")
elif selected_tab == "Assistant IA":
    st.caption("Métriques d'utilisation de l'assistant intelligent.")

# ── Variables globales par défaut ──────────────────────────────────────────────
selected_service = "Tous les services"
selected_period = "Toute la période disponible"
filtered_usage = data.usage_events.copy()
current_window = None
kpi_usage = filtered_usage
previous_usage = pd.DataFrame()

def prepare_evolution_interpretation(
    trend_df: pd.DataFrame,
    selected_service: str,
    selected_metric_label: str,
    selected_metric: str,
) -> dict:
    """Génère une interprétation contrôlée du graphique d'évolution."""

    if trend_df.empty or selected_metric not in trend_df.columns:
        return {
            "observation": (
                "Le graphique ne contient pas assez de données avec les filtres actuels."
            ),
            "interpretation": (
                "L’absence de données peut venir d’une période trop restrictive, "
                "d’un service non disponible ou d’un problème de source."
            ),
            "recommendation": (
                "Élargir la période d’analyse ou vérifier la disponibilité des données "
                "pour le service sélectionné."
            ),
        }

    working_df = trend_df.copy()

    if selected_service != "Tous les services" and "service" in working_df.columns:
        working_df = working_df[
            working_df["service"].astype(str) == str(selected_service)
        ]

    if working_df.empty or "date" not in working_df.columns:
        return {
            "observation": (
                "Aucune tendance exploitable n’est disponible pour cette sélection."
            ),
            "interpretation": (
                "Le service ou le KPI sélectionné ne contient pas suffisamment de points "
                "pour analyser une évolution."
            ),
            "recommendation": (
                "Vérifier les filtres appliqués ou choisir un autre KPI d’évolution."
            ),
        }

    working_df["date"] = pd.to_datetime(working_df["date"], errors="coerce")
    working_df = working_df.dropna(subset=["date", selected_metric])

    if selected_metric == "frequency":
        daily_series = (
            working_df.groupby("date", as_index=False)[selected_metric]
            .mean()
            .sort_values("date")
        )
    else:
        daily_series = (
            working_df.groupby("date", as_index=False)[selected_metric]
            .sum()
            .sort_values("date")
        )

    if daily_series.empty:
        return {
            "observation": (
                "Le graphique ne contient pas de valeur exploitable pour le KPI sélectionné."
            ),
            "interpretation": (
                "Le KPI choisi est présent dans le dashboard, mais aucune valeur valide "
                "n’est disponible sur la période filtrée."
            ),
            "recommendation": (
                "Tester un autre KPI ou vérifier la qualité de la donnée source."
            ),
        }

    current_value = float(daily_series.iloc[-1][selected_metric])
    previous_value = None

    if len(daily_series) >= 2:
        previous_value = float(daily_series.iloc[-2][selected_metric])

    start_date = daily_series["date"].min().strftime("%d/%m/%Y")
    end_date = daily_series["date"].max().strftime("%d/%m/%Y")

    def format_value(value: float) -> str:
        if selected_metric == "frequency":
            return f"{value:.1f}"
        return f"{int(round(value)):,}".replace(",", " ")

    if selected_service == "Tous les services":
        service_scope = "l’ensemble des services sélectionnés"
    else:
        service_scope = f"le service {selected_service}"

    observation = (
        f"Le graphique présente l’évolution du KPI {selected_metric_label} pour "
        f"{service_scope}, sur la période du {start_date} au {end_date}. "
        f"La dernière valeur observée est {format_value(current_value)}."
    )

    variation_percent = None

    if previous_value is not None and previous_value != 0:
        variation_percent = ((current_value - previous_value) / previous_value) * 100

    if variation_percent is None:
        trend_sentence = (
            "Il n’y a pas assez de points précédents pour calculer une variation fiable."
        )
    elif variation_percent >= 20:
        trend_sentence = (
            f"Le KPI est en forte hausse par rapport au point précédent "
            f"({variation_percent:.1f} %)."
        )
    elif variation_percent <= -20:
        trend_sentence = (
            f"Le KPI est en forte baisse par rapport au point précédent "
            f"({variation_percent:.1f} %)."
        )
    elif abs(variation_percent) < 5:
        trend_sentence = (
            f"Le KPI est relativement stable par rapport au point précédent "
            f"({variation_percent:.1f} %)."
        )
    elif variation_percent > 0:
        trend_sentence = (
            f"Le KPI est en hausse modérée par rapport au point précédent "
            f"({variation_percent:.1f} %)."
        )
    else:
        trend_sentence = (
            f"Le KPI est en baisse modérée par rapport au point précédent "
            f"({variation_percent:.1f} %)."
        )

    if selected_metric == "dau":
        metric_explanation = (
            "Le DAU mesure l’activité quotidienne. Il est sensible aux incidents, "
            "aux jours creux et aux variations ponctuelles de trafic."
        )
    elif selected_metric == "wau":
        metric_explanation = (
            "Le WAU donne une lecture plus stable de l’usage hebdomadaire. "
            "Il permet d’observer la régularité d’utilisation sur plusieurs jours."
        )
    elif selected_metric == "mau":
        metric_explanation = (
            "Le MAU représente la base mensuelle active. Il est utile pour suivre "
            "l’adoption globale, mais il ne montre pas toujours la fréquence réelle d’usage."
        )
    elif selected_metric == "events":
        metric_explanation = (
            "Le volume d’événements mesure l’intensité d’activité, mais il ne doit pas "
            "être confondu avec le nombre d’utilisateurs actifs."
        )
    else:
        metric_explanation = (
            "La fréquence moyenne indique l’intensité d’usage par utilisateur actif. "
            "Une valeur élevée peut refléter un usage fort ou une concentration de "
            "l’activité sur quelques profils."
        )

    interpretation = f"{trend_sentence} {metric_explanation}"

    if variation_percent is not None and variation_percent <= -20:
        recommendation = (
            "Analyser les dates de baisse et les corréler avec des incidents techniques, "
            "des changements fonctionnels, des périodes creuses ou un problème de tracking."
        )
    elif variation_percent is not None and variation_percent >= 20:
        recommendation = (
            "Identifier la cause de la hausse : campagne de communication, événement métier, "
            "nouvelle fonctionnalité ou pic de trafic. Vérifier si cette progression est durable."
        )
    else:
        recommendation = (
            "Continuer le suivi sur plusieurs périodes et comparer cette tendance avec "
            "les autres services. Pour conclure sur l’adoption réelle, compléter la population "
            "éligible par service."
        )

    return {
        "observation": observation,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }

def prepare_entity_usage_interpretation(entity_usage_df: pd.DataFrame) -> dict:
    """Génère une interprétation contrôlée du tableau Usage par entité / campus."""

    if entity_usage_df.empty:
        return {
            "observation": (
                "Le tableau Usage par entité / campus ne contient pas de données "
                "avec les filtres actuels."
            ),
            "interpretation": (
                "L'absence de données empêche d'analyser la répartition de l'usage "
                "par organisation, campus ou entité."
            ),
            "recommendation": (
                "Vérifier les filtres appliqués et la disponibilité du mapping "
                "utilisateur vers entité, campus ou direction."
            ),
        }

    working_df = entity_usage_df.copy()

    services_count = 0
    if "Service" in working_df.columns:
        services_count = working_df["Service"].dropna().astype(str).nunique()

    total_active_users = 0
    if "Utilisateurs actifs" in working_df.columns:
        active_users_series = pd.to_numeric(
            working_df["Utilisateurs actifs"],
            errors="coerce",
        ).fillna(0)
        total_active_users = int(active_users_series.sum())
    else:
        active_users_series = pd.Series(dtype=float)

    has_entity_column = "Entité / campus" in working_df.columns
    has_status_column = "Statut données" in working_df.columns

    has_missing_mapping = False

    if has_entity_column:
        entities = (
            working_df["Entité / campus"]
            .fillna("Non renseigné")
            .replace({"Unknown": "Non renseigné", "": "Non renseigné"})
            .astype(str)
            .tolist()
        )
        has_missing_mapping = "Non renseigné" in entities

    if has_status_column:
        status_values = (
            working_df["Statut données"]
            .fillna("")
            .astype(str)
            .str.lower()
            .tolist()
        )
        has_missing_mapping = has_missing_mapping or any(
            "mapping" in status or "manquant" in status
            for status in status_values
        )

    top_entity_text = "aucune entité principale identifiable"

    if (
        has_entity_column
        and "Service" in working_df.columns
        and "Utilisateurs actifs" in working_df.columns
        and not active_users_series.empty
    ):
        working_df["_active_users_numeric"] = active_users_series
        top_row = working_df.sort_values(
            "_active_users_numeric",
            ascending=False,
        ).iloc[0]

        top_entity = str(top_row.get("Entité / campus", "Non renseigné"))
        top_service = str(top_row.get("Service", "service non renseigné"))
        top_active_users = int(top_row.get("_active_users_numeric", 0))

        top_entity_text = (
            f"{top_entity} pour {top_service} avec "
            f"{top_active_users:,} utilisateurs actifs observés"
        ).replace(",", " ")

        working_df = working_df.drop(columns=["_active_users_numeric"])

    if services_count == 0:
        service_scope = "aucun service"
    elif services_count == 1:
        service_scope = "un service"
    else:
        service_scope = f"{services_count} services"

    observation = (
        f"Le tableau présente la répartition de l'usage par entité ou campus "
        f"pour {service_scope}. Le total observé est de "
        f"{total_active_users:,} utilisateurs actifs, et la principale ligne "
        f"d'usage est : {top_entity_text}."
    ).replace(",", " ")

    if has_missing_mapping:
        interpretation = (
            "L'analyse par entité ou campus est partielle, car certaines lignes "
            "contiennent un mapping organisationnel manquant ou non renseigné. "
            "Cela signifie que l'usage est bien observé, mais qu'il ne peut pas "
            "encore être totalement rattaché à une organisation."
        )
    else:
        interpretation = (
            "La répartition par entité ou campus est exploitable pour comparer "
            "les niveaux d'usage entre organisations. Les écarts observés peuvent "
            "indiquer des différences d'adoption, de besoin métier ou de maturité "
            "numérique."
        )

    recommendation = (
        "Compléter le mapping utilisateur vers entité, campus ou direction, puis "
        "ajouter la population éligible par service. Cela permettra de passer "
        "d'une lecture d'usage observé à une vraie mesure du taux d'adoption par "
        "organisation."
    )

    return {
        "observation": observation,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }

def prepare_top_interactions_interpretation(top_interactions_df: pd.DataFrame) -> dict:
    """Génère une interprétation contrôlée du tableau Top interactions."""

    if top_interactions_df.empty:
        return {
            "observation": (
                "Le tableau Top interactions ne contient pas de données avec les filtres actuels."
            ),
            "interpretation": (
                "L'absence d'interactions empêche d'identifier les pages, routes, API "
                "ou actions métier les plus utilisées."
            ),
            "recommendation": (
                "Vérifier les filtres appliqués et la disponibilité des logs ou événements "
                "d'usage pour les services sélectionnés."
            ),
        }

    working_df = top_interactions_df.copy()

    services_count = 0
    if "Service" in working_df.columns:
        services_count = working_df["Service"].dropna().astype(str).nunique()

    interactions_count = len(working_df)

    events_series = pd.Series(dtype=float)
    total_events = 0

    if "Événements" in working_df.columns:
        events_series = pd.to_numeric(
            working_df["Événements"],
            errors="coerce",
        ).fillna(0)
        total_events = int(events_series.sum())

    top_interaction_text = "aucune interaction principale identifiable"
    top_share = None
    top_type = "type non renseigné"
    top_service = "service non renseigné"
    top_interaction = "interaction non renseignée"
    top_events = 0

    if not events_series.empty and events_series.sum() > 0:
        working_df["_events_numeric"] = events_series
        top_row = working_df.sort_values(
            "_events_numeric",
            ascending=False,
        ).iloc[0]

        top_service = str(top_row.get("Service", "service non renseigné"))
        top_type = str(top_row.get("Type d'interaction", "type non renseigné"))
        top_interaction = str(top_row.get("Interaction", "interaction non renseignée"))
        top_events = int(top_row.get("_events_numeric", 0))

        if "Part des événements (%)" in working_df.columns:
            top_share_value = str(top_row.get("Part des événements (%)", "")).replace("%", "")
            top_share = pd.to_numeric(top_share_value, errors="coerce")

        if pd.isna(top_share):
            top_share = None

        if top_share is not None:
            top_interaction_text = (
                f"{top_interaction} pour {top_service}, avec {top_events:,} événements "
                f"et {float(top_share):.2f} % des événements affichés"
            )
        else:
            top_interaction_text = (
                f"{top_interaction} pour {top_service}, avec {top_events:,} événements"
            )

        working_df = working_df.drop(columns=["_events_numeric"])

    if services_count == 0:
        service_scope = "aucun service"
    elif services_count == 1:
        service_scope = "un service"
    else:
        service_scope = f"{services_count} services"

    observation = (
        f"Le tableau présente les principales interactions observées pour {service_scope}. "
        f"{interactions_count} interactions sont affichées, avec un total de "
        f"{total_events:,} événements dans ce classement. "
        f"L'interaction dominante est : {top_interaction_text}."
    )

    if top_share is not None and float(top_share) >= 50:
        concentration_sentence = (
            "Une interaction concentre une part très importante de l'activité. "
            "Cela indique qu'un parcours ou une fonctionnalité joue un rôle central "
            "dans l'usage du service."
        )
    elif top_share is not None and float(top_share) >= 20:
        concentration_sentence = (
            "L'activité est partiellement concentrée sur quelques interactions principales. "
            "Ces interactions représentent des parcours importants à surveiller."
        )
    else:
        concentration_sentence = (
            "L'activité semble répartie entre plusieurs interactions. "
            "Cela peut indiquer des usages plus diversifiés selon les parcours."
        )

    top_type_lower = top_type.lower()

    if "api" in top_type_lower:
        type_sentence = (
            "La présence d'API parmi les interactions principales montre que la performance "
            "backend et la stabilité des endpoints sont importantes pour l'expérience utilisateur."
        )
    elif "action" in top_type_lower:
        type_sentence = (
            "La présence d'actions métier parmi les interactions principales montre que "
            "l'analyse doit être reliée aux processus fonctionnels du service."
        )
    elif "page" in top_type_lower or "route" in top_type_lower:
        type_sentence = (
            "La présence de pages ou routes dominantes permet d'identifier les points "
            "d'entrée et parcours les plus consultés."
        )
    else:
        type_sentence = (
            "Les interactions affichées donnent une première lecture des usages dominants, "
            "mais leur signification métier doit être validée avec l'équipe applicative."
        )

    interpretation = f"{concentration_sentence} {type_sentence}"

    if top_share is not None and float(top_share) >= 50:
        recommendation = (
            "Prioriser l'optimisation de l'interaction dominante : performance, stabilité, "
            "ergonomie et monitoring. Vérifier aussi si cette concentration est normale "
            "du point de vue métier ou si elle révèle un parcours trop répétitif."
        )
    elif "api" in top_type_lower:
        recommendation = (
            "Surveiller les routes API les plus sollicitées, analyser leurs temps de réponse "
            "et envisager du caching ou une optimisation backend si le volume reste élevé."
        )
    elif "action" in top_type_lower:
        recommendation = (
            "Analyser les actions métier les plus fréquentes avec les équipes fonctionnelles "
            "afin d'identifier les parcours à simplifier, automatiser ou mieux monitorer."
        )
    else:
        recommendation = (
            "Comparer ces interactions sur plusieurs périodes pour distinguer les usages "
            "récurrents des pics ponctuels, puis prioriser les parcours les plus critiques."
        )

    return {
        "observation": observation,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }

def prepare_data_quality_interpretation(data_quality_df: pd.DataFrame) -> dict:
    """Génère une interprétation contrôlée du bloc Données manquantes / Qualité des données."""

    if data_quality_df.empty:
        return {
            "observation": (
                "La section Qualité des données ne contient aucune information avec "
                "les filtres actuels."
            ),
            "interpretation": (
                "Il n'est pas possible d'évaluer la fiabilité de l'analyse sans données "
                "de qualité disponibles par service."
            ),
            "recommendation": (
                "Vérifier la disponibilité des sources de données et relancer l'analyse "
                "sur une période contenant des événements exploitables."
            ),
        }

    working_df = data_quality_df.copy()

    services_count = 0
    if "Service" in working_df.columns:
        services_count = working_df["Service"].dropna().astype(str).nunique()

    missing_population_count = 0
    if "Population éligible" in working_df.columns:
        population_values = (
            working_df["Population éligible"]
            .fillna("")
            .astype(str)
            .str.lower()
        )
        missing_population_count = int(
            population_values.str.contains("manquante").sum()
        )

    non_calculable_usage_count = 0

    usage_rate_column = next(
        (
            column
            for column in working_df.columns
            if "taux" in str(column).lower()
            and "utilisation" in str(column).lower()
        ),
        None,
    )

    if usage_rate_column is not None:
        usage_values = (
            working_df[usage_rate_column]
            .fillna("")
            .astype(str)
            .str.lower()
        )

        non_calculable_usage_count = int(
            usage_values.str.contains("non calculable", regex=False).sum()
        )

    if non_calculable_usage_count == 0 and missing_population_count > 0:
        non_calculable_usage_count = missing_population_count

    missing_mapping_count = 0
    if "Entité / campus" in working_df.columns:
        entity_values = (
            working_df["Entité / campus"]
            .fillna("")
            .astype(str)
            .str.lower()
        )
        missing_mapping_count = int(
            entity_values.str.contains("mapping").sum()
            + entity_values.str.contains("manquant").sum()
        )

    partial_or_incomplete_count = 0
    if "Statut global" in working_df.columns:
        status_values = (
            working_df["Statut global"]
            .fillna("")
            .astype(str)
            .str.lower()
        )
        partial_or_incomplete_count = int(
            status_values.isin(["partiel", "à compléter"]).sum()
        )

    available_interactions_count = 0
    if "Interactions" in working_df.columns:
        interactions_values = (
            working_df["Interactions"]
            .fillna("")
            .astype(str)
            .str.lower()
        )
        available_interactions_count = int(
            interactions_values.str.contains("disponibles").sum()
        )

    if services_count == 0:
        service_scope = "aucun service"
    elif services_count == 1:
        service_scope = "un service"
    else:
        service_scope = f"{services_count} services"

    observation = (
        f"La section évalue la qualité des données pour {service_scope}. "
        f"{partial_or_incomplete_count} service(s) présentent des données partielles "
        f"ou à compléter. Le taux d'utilisation est non calculable pour "
        f"{non_calculable_usage_count} service(s), principalement à cause de la "
        f"population éligible manquante."
    )

    if missing_population_count > 0 and missing_mapping_count > 0:
        interpretation = (
            "Les données d'usage sont exploitables pour mesurer l'activité observée, "
            "mais elles ne suffisent pas encore pour mesurer une adoption métier complète. "
            "La population éligible manque pour calculer le taux d'utilisation réel, "
            "et le mapping organisationnel manquant limite l'analyse par entité ou campus."
        )
    elif missing_population_count > 0:
        interpretation = (
            "Les données d'usage sont disponibles, mais le taux d'utilisation réel "
            "reste non calculable sans population éligible par service. L'analyse mesure "
            "donc l'usage observé, pas encore l'adoption complète."
        )
    elif missing_mapping_count > 0:
        interpretation = (
            "L'analyse globale de l'usage est possible, mais la lecture par entité ou "
            "campus reste partielle car le mapping organisationnel est incomplet."
        )
    elif partial_or_incomplete_count > 0:
        interpretation = (
            "Certaines informations restent partielles. Les résultats doivent être lus "
            "avec prudence avant de conclure sur le niveau réel d'adoption."
        )
    else:
        interpretation = (
            "Les principales données nécessaires semblent disponibles pour les services "
            "affichés. L'analyse peut être exploitée plus directement, sous réserve de "
            "validation métier des sources."
        )

    if missing_population_count > 0 and missing_mapping_count > 0:
        recommendation = (
            "Prioriser deux référentiels : la population éligible par service et le "
            "mapping utilisateur vers entité, campus ou direction. Ces deux éléments "
            "permettront de calculer un vrai taux d'adoption et de comparer les usages "
            "entre organisations."
        )
    elif missing_population_count > 0:
        recommendation = (
            "Collecter la population éligible par service afin de transformer les KPI "
            "d'usage observé en taux d'utilisation réel."
        )
    elif missing_mapping_count > 0:
        recommendation = (
            "Compléter le mapping utilisateur vers entité, campus ou direction afin de "
            "fiabiliser l'analyse organisationnelle de l'adoption."
        )
    else:
        recommendation = (
            "Maintenir le contrôle qualité des données et valider les définitions des "
            "indicateurs avec les équipes métier avant d'industrialiser les alertes."
        )

    return {
        "observation": observation,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }

# ── Pages ──────────────────────────────────────────────────────────────────────

if selected_tab == "Vue d'ensemble":
    # ── Filtres Globaux ────────────────────────────────────────────────────────────
    with st.container(border=True):
        control_service, control_period = st.columns([1, 1])
    
        with control_service:
            selected_service = st.selectbox(
                "Service",
                ["Tous les services"] + available_services,
                index=0,
                key="global_service_filter",
            )

        # Le service pilote le dataset servant à déterminer la période disponible.
        if selected_service == "Tous les services":
            service_usage = data.usage_events.copy()
        else:
            service_usage = data.usage_events[
                data.usage_events["service"].astype(str).eq(selected_service)
            ].copy()

        available_start, available_end = get_available_date_bounds(service_usage)

        with control_period:
            selected_period = st.selectbox(
                "Période",
                PERIOD_OPTIONS,
                index=0,
                key="global_period_filter",
            )

        custom_start = None
        custom_end = None

        if (
            selected_period == "Période personnalisée"
            and available_start is not None
            and available_end is not None
        ):
            custom_col1, custom_col2 = st.columns(2)

            with custom_col1:
                custom_start = st.date_input(
                    "Du",
                    value=available_start.date(),
                    min_value=available_start.date(),
                    max_value=available_end.date(),
                    key="custom_start_date",
                )

            with custom_col2:
                custom_end = st.date_input(
                    "Au",
                    value=available_end.date(),
                    min_value=available_start.date(),
                    max_value=available_end.date(),
                    key="custom_end_date",
                )

    if available_start is None or available_end is None:
        st.warning("Aucune donnée datée disponible avec cette sélection.")
        filtered_usage = service_usage.iloc[0:0].copy()
        current_window = None

    else:
        current_window = resolve_period(
            selected_period,
            available_start,
            available_end,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        filtered_usage = apply_date_filter(
            service_usage,
            current_window,
        )

        if selected_service == "Tous les services" and selected_period == "Dernière date disponible":
            period_info = "Période propre à chaque service"
        elif selected_service == "Tous les services" and selected_period == "Toute la période disponible":
            period_info = "Périodes disponibles différentes selon les services"
        elif selected_period == "Dernière date disponible":
            period_info = f"{current_window.start_date.strftime('%d/%m/%Y')}"
        elif current_window.start_date == current_window.end_date:
            period_info = f"{current_window.start_date.strftime('%d/%m/%Y')}"
        else:
            period_info = f"{current_window.start_date.strftime('%d/%m/%Y')} — {current_window.end_date.strftime('%d/%m/%Y')}"
        
        st.caption(f"**Période utilisée :** {period_info}")
    
        st.subheader("Ce qui mérite votre attention")
        signals = []
    
        if filtered_usage.empty:
            signals.append({
                "type": "error",
                "title": "Aucune donnée disponible",
                "message": "Aucune donnée disponible sur la période sélectionnée.",
                "action": None
            })
        else:
            if selected_service == "Tous les services":
                latest_dates = {}
                for srv in available_services:
                    srv_usage = data.usage_events[data.usage_events["service"].astype(str).eq(srv)]
                    if not srv_usage.empty:
                        _, srv_end = get_available_date_bounds(srv_usage)
                        if srv_end:
                            latest_dates[srv] = srv_end.strftime('%d/%m/%Y')
            
                if len(set(latest_dates.values())) > 1:
                    details = "<br>".join([f"<strong>{s}</strong> : {d}" for s, d in latest_dates.items()])
                    signals.append({
                        "type": "warning",
                        "title": "Fraîcheur des données hétérogène",
                        "message": f"Les comparaisons entre services doivent tenir compte des différences de fraîcheur.<br><br>{details}",
                        "action": None
                    })
            else:
                if current_window is not None and current_window.start_date == current_window.end_date:
                    signals.append({
                        "type": "info",
                        "title": "Historique limité",
                        "message": "Une seule journée est sélectionnée.",
                        "action": None
                    })
                elif current_window is not None:
                    available_end_ts = pd.Timestamp(available_end).normalize()
                    window_end_ts = pd.Timestamp(current_window.end_date).normalize()
                    staleness_days = (window_end_ts - available_end_ts).days

                    if staleness_days > 7:
                        signals.append({
                            "type": "warning",
                            "title": "Dernière donnée ancienne",
                            "message": f"La dernière donnée date du {available_end.strftime('%d/%m/%Y')}.",
                            "action": None
                        })

            if selected_service.lower() == "booking":
                signals.append({
                    "type": "info",
                    "title": "Adoption à analyser par module",
                    "message": "La population éligible est disponible par module. Aucun taux global Booking n'est calculé afin d'éviter de sommer des populations qui peuvent se chevaucher.",
                    "action": "Consulter l'adoption par module et par campus."
                })
            else:
                signals.append({
                    "type": "info",
                    "title": "Taux d'adoption non disponible",
                    "message": "Population éligible manquante.",
                    "action": "Action : compléter le référentiel des utilisateurs éligibles."
                })
        
            dept_df = departmental_breakdown(filtered_usage)
            if not dept_df.empty and "department" in dept_df.columns:
                total_events = dept_df["events"].sum()
                unknown_events = dept_df[dept_df["department"] == "Unknown"]["events"].sum()
                if total_events > 0 and (unknown_events / total_events) > 0.5:
                    signals.append({
                        "type": "warning",
                        "title": "Analyse organisationnelle limitée",
                        "message": "Mapping utilisateur — entité/campus manquant.",
                        "action": "Action : fournir le mapping utilisateur — organisation."
                    })

        for sig in signals[:2]:
            st.markdown(
                f'''
                <div class="attention-card attention-{sig["type"]}">
                    <h4>{sig["title"]}</h4>
                    <p>{sig["message"]}</p>
                    {f'<div class="attention-action">{sig["action"]}</div>' if sig["action"] else ""}
                </div>
                ''',
                unsafe_allow_html=True
            )

    if current_window is not None and current_window.label not in ("Toute la période disponible", "Dernière date disponible"):
        kpi_reference_date = current_window.end_date
    else:
        kpi_reference_date = None

    if selected_period == "Dernière date disponible":
        kpi_usage = service_usage.copy()
    else:
        kpi_usage = filtered_usage

    previous_usage = pd.DataFrame()

    if current_window is not None:
        previous_window = get_previous_window(current_window)

        previous_usage = apply_date_filter(
            service_usage,
            previous_window,
        )



    if current_window is not None:
        service_label = selected_service

        st.caption(
            f"{service_label}  "
            f"{current_window.start_date.strftime('%d/%m/%Y')}  "
            f"{current_window.end_date.strftime('%d/%m/%Y')}"
        )

    dashboard_adoption_vm = dashboard_service.get_adoption_view(
        filtered_usage, 
        reference_date=kpi_reference_date,
        kpi_usage=kpi_usage
    )

    st.subheader("Santé de l'adoption")
    if selected_service != "Tous les services":
        st.caption("Activité récente et régularité d'usage du service.")
    else:
        st.caption("Vue d'ensemble des services disponibles.")

    def render_kpi_card(title: str, value: str, subtitle: str) -> None:
        st.markdown(
            f'''
            <div class="kpi-card">
                <div class="kpi-card-title">{title}</div>
                <div class="kpi-card-value">{value}</div>
                <div class="kpi-card-subtitle">{subtitle}</div>
            </div>
            ''',
            unsafe_allow_html=True
        )

    if selected_service == "Tous les services":
        overview = dashboard_service.get_global_overview(
            filtered_usage, 
            available_services, 
            reference_date=kpi_reference_date,
            kpi_usage=kpi_usage
        )
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            render_kpi_card("Services suivis", str(overview["services_suivis"]), "Total configuré")
        with kpi2:
            render_kpi_card("Services avec données", str(overview["services_avec_donnees"]), "Actifs sur la période")
        with kpi3:
            render_kpi_card("Volume observé", f"{overview['volume_observe']:,}".replace(",", " "), "Événements totaux")
        with kpi4:
            render_kpi_card("Fraîcheur", overview["fraicheur"], "Dernière donnée")
            
        st.markdown(
            "<p style='font-size: 0.9em; color: gray; font-style: italic; margin-top: 12px;'>"
            "Les utilisateurs ne sont pas agrégés entre services car les "
            "sources ne garantissent pas une identité utilisateur commune. "
            "Les KPI sont donc présentés séparément par service."
            "</p>",
            unsafe_allow_html=True
        )
        
        if overview["table_data"]:
            st.dataframe(pd.DataFrame(overview["table_data"]), hide_index=True)
            
    else:

        metrics = dashboard_adoption_vm.metrics
        has_data = not filtered_usage.empty
        
        is_booking = (selected_service.lower() == "booking")

        freq_val = "Non disponible"
        freq_subtitle = "Fréquence comparable non disponible"
        
        if has_data and is_booking:
            extended = dashboard_service.get_service_extended_analytics(
                selected_service, 
                reference_date=kpi_reference_date
            )
            if extended and extended.status != "not_available" and extended.usage:
                # Override metrics for Booking to ensure a single source of truth
                metrics.update({
                    "dau": extended.usage.get("dau", metrics.get("dau")),
                    "wau": extended.usage.get("wau", metrics.get("wau")),
                    "mau": extended.usage.get("mau", metrics.get("mau")),
                    "avg_active_days_per_active_user_30d": extended.usage.get("avg_active_days_per_active_user_30d"),
                })
                avg_days = extended.usage.get("avg_active_days_per_active_user_30d")
                if avg_days is not None:
                    freq_val = f"{avg_days}".replace(".", ",") + " jours"
                    freq_subtitle = "Jours actifs moyens / utilisateur"

        if has_data:
            dau_val = f"{int(metrics.get('dau', 0)):,}".replace(",", " ")
            wau_val = f"{int(metrics.get('wau', 0)):,}".replace(",", " ")
            mau_val = f"{int(metrics.get('mau', 0)):,}".replace(",", " ")
        else:
            dau_val = "Non disponible"
            wau_val = "Non disponible"
            mau_val = "Non disponible"

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        with kpi1:
            render_kpi_card("DAU", dau_val, "Actifs du jour")
        with kpi2:
            render_kpi_card("WAU", wau_val, "Actifs sur 7 jours")
        with kpi3:
            render_kpi_card("MAU", mau_val, "Actifs sur 30 jours")
        with kpi4:
            render_kpi_card("Fréquence d'usage", freq_val, freq_subtitle)

        if has_data:
            kpi_insight = prepare_kpi_interpretation(
                metrics,
                filtered_usage,
                is_booking=is_booking,
            )

            next_actions = prepare_kpi_recommendations(metrics)

            st.markdown("### Insight stratégique")

            st.markdown(
                f'''
                <div class="strategic-card">
                    <strong>Ce qui se passe</strong><br>
                    {kpi_insight.get("observation", "")}
                    <br><br>
                    <strong>Pourquoi cela compte</strong><br>
                    {kpi_insight.get("interpretation", "")}
                </div>
                ''',
                unsafe_allow_html=True,
            )

            if next_actions:
                actions_html = "".join(
                    f"<li>{action}</li>"
                    for action in next_actions[:3]
                )

                st.markdown(
                    f'''
                    <div class="next-action">
                        <strong>Next Actions</strong>
                        <ul>
                            {actions_html}
                        </ul>
                    </div>
                    ''',
                    unsafe_allow_html=True,
                )

            advanced_kpis = compute_advanced_adoption_kpis(
                dashboard_adoption_vm.metrics,
            )

            advanced_kpi_insight = prepare_advanced_kpis_interpretation(
                advanced_kpis,
                dashboard_adoption_vm.metrics,
            )
            advanced_kpi_insight = add_recommendations_to_insight(
                advanced_kpi_insight,
                prepare_advanced_kpi_recommendations(advanced_kpis),
            )

            advanced_title_col, advanced_insight_col = st.columns([4, 1])

            with advanced_title_col:
                st.caption("Indicateurs dérivés de récurrence")

            with advanced_insight_col:
                with st.popover("💡 Interprétation IA"):
                    render_interpretation_popover(advanced_kpi_insight)
        
            with st.container(horizontal=True):
                st.metric(
                    "Stickiness DAU/MAU",
                    format_optional_percentage(
                        advanced_kpis["stickiness_dau_mau"],
                    ),
                    border=True,
                )

                st.metric(
                    "Récurrence WAU/MAU",
                    format_optional_percentage(
                        advanced_kpis["weekly_recurrence_wau_mau"],
                    ),
                    border=True,
                )


    # ── Évolution de l’usage ──────────────────────────────────────────────────

    trend_start = current_window.start_date if current_window is not None and selected_period not in ("Toute la période disponible", "Dernière date disponible") else None
    trend_end = current_window.end_date if current_window is not None and selected_period not in ("Toute la période disponible", "Dernière date disponible") else None

    service_bounds = {}
    if not data.usage_events.empty and "service" in data.usage_events.columns:
        for srv in data.usage_events["service"].dropna().unique():
            srv_usage = data.usage_events[data.usage_events["service"] == srv]
            if not srv_usage.empty:
                srv_min, srv_max = get_available_date_bounds(srv_usage)
                if srv_min and srv_max:
                    service_bounds[srv] = (srv_min, srv_max)

    unified_trend = build_unified_adoption_trend(
        filtered_usage, 
        start_date=trend_start, 
        end_date=trend_end, 
        service_bounds=service_bounds
    )

    trend_warning = dashboard_service.get_trend_warning_message(filtered_usage, selected_service)
    if trend_warning and selected_period != "Dernière date disponible":
        st.info(trend_warning)

    with st.container(border=True):
        if unified_trend.empty:
            st.subheader("Évolution de l’usage")
            st.info("Non disponible")
            st.caption("Aucune donnée observée sur la période sélectionnée.")
        else:
            is_all_services_view = (selected_service == "Tous les services")

            evolution_title_col, metric_select_col = st.columns(
                [3, 1],
                vertical_alignment="center",
            )

            with evolution_title_col:
                st.subheader("Évolution de l’usage")
                st.caption("Suivre l'activité dans le temps et repérer les variations.")

            with metric_select_col:
                metric_options = {
                    "Utilisateurs actifs": "dau",
                    "Événements observés": "events"
                }
                selected_metric_label = st.selectbox(
                    "Métrique",
                    options=list(metric_options.keys()),
                    index=0,
                    key="unified_trend_kpi",
                    label_visibility="collapsed"
                )

            selected_kpi = metric_options[selected_metric_label]

            evolution_interpretation = prepare_evolution_interpretation(
                unified_trend,
                selected_service,
                selected_metric_label,
                selected_kpi,
            )
            evolution_interpretation = add_recommendations_to_insight(
                evolution_interpretation,
                prepare_evolution_recommendations(
                    evolution_data=unified_trend,
                    selected_metric=selected_metric_label,
                    selected_service=selected_service,
                ),
            )
            
            with st.popover("💡 Interprétation IA"):
                render_interpretation_popover(evolution_interpretation)

            trend_to_display = unified_trend.copy()

            if not is_all_services_view:
                trend_to_display = trend_to_display[
                    trend_to_display["service"] == selected_service
                ]

            if selected_period == "Dernière date disponible":
                if is_all_services_view:
                    st.info(
                        "Le graphique d'évolution n'est pas affiché car la dernière "
                        "date disponible varie selon les services.\n"
                        "Afficher une évolution combinée serait incohérent."
                    )
                else:
                    st.info("Une seule journée est sélectionnée.\n"
                            "Une tendance temporelle ne peut pas être analysée.")
            else:
                if trend_to_display.empty:
                    st.info("Non disponible")
                    st.caption("Aucune donnée observée sur la période sélectionnée pour ce service.")
                else:
                    fig = px.line(
                        trend_to_display,
                        x="date",
                        y=selected_kpi,
                        color="service",
                        labels={"date": "Date", selected_kpi: selected_metric_label, "service": "Service"},
                        markers=True,
                        color_discrete_map={
                            "Booking": "#1f77d0",
                            "Learning Center": "#ff8a00",
                            "Ecommerce Demo": "#2ca02c"
                        }
                    )
                    
                    fig.update_layout(
                        height=360,
                        margin=dict(l=0, r=0, t=20, b=0),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=-0.2,
                            xanchor="center",
                            x=0.5,
                            title=""
                        )
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
    # ── Usage par entité / campus ──────────────────────────────────────────────

    dept_df = departmental_breakdown(filtered_usage)
    unified_entity_usage = prepare_unified_entity_usage_table(dept_df)

    with st.container(border=True):
        entity_title_col, entity_interpretation_col = st.columns(
            [4, 1],
            vertical_alignment="center",
        )

        with entity_title_col:
            st.subheader("Usage observé par organisation")

        entity_usage_interpretation = prepare_entity_usage_interpretation(
            unified_entity_usage,
        )
        entity_usage_interpretation = add_recommendations_to_insight(
            entity_usage_interpretation,
            prepare_entity_usage_recommendations(unified_entity_usage),
        )

        with entity_interpretation_col:
            with st.popover("💡 Interprétation IA"):
                render_interpretation_popover(entity_usage_interpretation)

        st.caption(
            "Table commune appliquée à tous les services. "
            "Les champs indisponibles restent visibles afin de distinguer les données calculées "
            "des données manquantes."
        )

        if unified_entity_usage.empty:
            st.info("Aucune donnée disponible pour l’usage par organisation.")
        else:
            meaningful_rows = unified_entity_usage[
                unified_entity_usage["Entité / campus"] != "Non renseigné"
            ]
            
            if meaningful_rows.empty:
                st.info("Mapping organisationnel non disponible pour cette sélection.")
            elif len(meaningful_rows) < len(unified_entity_usage):
                st.info("Mapping partiel")
            st.dataframe(
                unified_entity_usage,
                hide_index=True,
                width="stretch",
                column_config={
                    "Utilisateurs actifs": st.column_config.NumberColumn(
                        "Utilisateurs actifs",
                        format="%d",
                    ),
                    "Événements": st.column_config.NumberColumn(
                        "Événements",
                        format="%d",
                    ),
                    "Événements / utilisateur": st.column_config.NumberColumn(
                        "Événements / utilisateur",
                        format="%.2f",
                    ),
                    "Part des utilisateurs actifs (%)": st.column_config.NumberColumn(
                        "Part des utilisateurs actifs (%)",
                        format="%.2f",
                    ),
                },
            )

    # ── Adoption par campus (Service spécifique) ──────────────────────────────
    
    if True:
        with st.container(border=True):
            st.subheader("Adoption par campus")
            st.caption("Comparer l'activité observée à la population éligible.")
            
            if selected_service == "Tous les services":
                st.info("Non disponible")
                st.caption("Sélectionnez un service pour analyser l'adoption par campus.")
            else:
                if current_window is not None:
                    reference_date = current_window.end_date
                    window_days = (current_window.end_date - current_window.start_date).days + 1
                else:
                    reference_date = None
                    window_days = 30
                    
                extended = dashboard_service.get_service_extended_analytics(
                    selected_service,
                    reference_date=reference_date,
                    window_days=window_days
                )
                
                if extended is None or extended.status == "not_available" or not extended.adoption_by_module:
                    st.info("Non disponible")
                    st.caption("Les données nécessaires à l'adoption par campus ne sont pas disponibles pour ce service.")
                else:
                    modules = [m["module"] for m in extended.adoption_by_module if "module" in m]
                    
                    if not modules:
                        st.info("Non disponible")
                        st.caption("Les données nécessaires à l'adoption par campus ne sont pas disponibles pour ce service.")
                    else:
                        default_idx = modules.index("HOUSING") if "HOUSING" in modules else 0
                        
                        selected_module = st.selectbox(
                            "Module",
                            options=modules,
                            index=default_idx,
                            key="adoption_campus_module_filter"
                        )
                        
                        if extended.adoption_by_campus:
                            campus_data = [row for row in extended.adoption_by_campus if row.get("module") == selected_module]
                            
                            if not campus_data:
                                st.info("Adoption par campus non disponible")
                                st.caption("Population éligible non fournie pour ce module.")
                            else:
                                display_rows = []
                                for row in campus_data:
                                    campus = row.get("campus", "Inconnu")
                                    active = row.get("active_users", 0)
                                    eligible = row.get("eligible_users", 0)
                                    rate = row.get("observed_adoption_rate")
                                    status = row.get("status")
                                    
                                    if status == "available" and rate is not None:
                                        if rate == 0:
                                            adoption_text = "0 %"
                                        else:
                                            adoption_text = f"{rate} %"
                                    elif status == "telemetry_unavailable":
                                        adoption_text = "Non disponible - télémétrie absente"
                                    elif status == "eligible_population_unavailable":
                                        adoption_text = "Non disponible - population éligible absente"
                                    else:
                                        adoption_text = "Non disponible"
                                    
                                    active_str = f"{int(active)} actif{'s' if active > 1 else ''}"
                                    eligible_str = f"{int(eligible)} éligible{'s' if eligible > 1 else ''}"
                                    
                                    display_rows.append({
                                        "Campus": campus,
                                        "Utilisateurs actifs": active_str,
                                        "Population éligible": eligible_str,
                                        "Adoption observée": adoption_text,
                                        "_sort_val": rate if rate is not None else -1
                                    })
                                
                                if display_rows:
                                    df_display = pd.DataFrame(display_rows)
                                    df_display = df_display.sort_values(by="_sort_val", ascending=False).drop(columns=["_sort_val"])
                                    
                                    st.dataframe(
                                        df_display,
                                        hide_index=True,
                                        width="stretch"
                                    )
                                else:
                                    st.info("Adoption par campus non disponible")
                                    st.caption("Population éligible non fournie pour ce module.")
                        else:
                            st.info("Adoption par campus non disponible")
                            st.caption("Population éligible non fournie pour ce module.")

    # ── Top interactions ──────────────────────────────────────────────────────

    if current_window is not None and data.web_logs is not None and not data.web_logs.empty:
        web_logs_ts_col = "timestamp" if "timestamp" in data.web_logs.columns else "event_timestamp"
        filtered_web_logs = apply_date_filter(data.web_logs, current_window, timestamp_column=web_logs_ts_col)
    else:
        filtered_web_logs = data.web_logs

    unified_top_interactions = prepare_unified_top_interactions_table(
        filtered_usage,
        web_logs_df=filtered_web_logs,
        top_n=15,
    )

    with st.container(border=True):
        top_title_col, top_interpretation_col = st.columns(
            [4, 1],
            vertical_alignment="center",
        )

        with top_title_col:
            st.subheader("Top interactions")

        top_interactions_interpretation = prepare_top_interactions_interpretation(
            unified_top_interactions,
        )
        top_interactions_interpretation = add_recommendations_to_insight(
            top_interactions_interpretation,
            prepare_top_interactions_recommendations(unified_top_interactions),
        )

        with top_interpretation_col:
            with st.popover("💡 Interprétation IA"):
                render_interpretation_popover(top_interactions_interpretation)

        st.caption(
            "Vue commune des pages, routes, API ou actions métier les plus fréquentes. "
            "Le type d’interaction permet d’utiliser une même structure pour tous les services."
        )

        if unified_top_interactions.empty:
            st.info("Aucune interaction disponible pour les filtres sélectionnés.")
        else:
            st.dataframe(
                unified_top_interactions,
                hide_index=True,
                width="stretch",
                column_config={
                    "Événements": st.column_config.NumberColumn(
                        "Événements",
                        format="%d",
                    ),
                    "Part des événements (%)": st.column_config.NumberColumn(
                        "Part des événements (%)",
                        format="%.2f",
                    ),
                },
            )

    # ── Synthèse Matomo / Ecommerce Demo ───────────────────────────────────────

    ecommerce_usage = filtered_usage[
        filtered_usage["service"].astype(str).str.lower().eq("ecommerce demo")
    ].copy()

    if not ecommerce_usage.empty:
        ecommerce_is_live = has_matomo_live_source(ecommerce_usage)
        ecommerce_has_matomo = has_matomo_source(ecommerce_usage)

        with st.container(border=True):
            st.subheader("Synthèse web analytics — Ecommerce Demo")

            if ecommerce_is_live:
                st.caption(
                    "Données détaillées extraites via Matomo "
                    "Live.getLastVisitsDetails et normalisées vers le modèle commun."
                )
                st.success(
                    "Mode d'extraction actif : RAW Matomo Live — visites, "
                    "sessions, actionDetails et pages consultées sont disponibles."
                )
            elif ecommerce_has_matomo:
                st.caption(
                    "Données collectées depuis Matomo et normalisées vers le modèle commun. "
                    "Les événements proviennent actuellement d'un export agrégé par page."
                )
                st.warning(
                    "Mode d'extraction actif : agrégé par page — suffisant pour "
                    "les top pages, mais limité pour l'analyse détaillée des parcours visiteurs."
                )
            else:
                st.caption(
                    "Données Ecommerce Demo normalisées vers le modèle commun."
                )

            ecommerce_total_events = len(ecommerce_usage)
            ecommerce_users = ecommerce_usage["user_id"].nunique()
            ecommerce_sessions = (
                ecommerce_usage["session_id"].nunique()
                if "session_id" in ecommerce_usage.columns
                else 0
            )
            ecommerce_pages = (
                ecommerce_usage["page"].nunique()
                if "page" in ecommerce_usage.columns
                else 0
            )

            ecommerce_col1, ecommerce_col2, ecommerce_col3, ecommerce_col4 = st.columns(4)

            ecommerce_col1.metric("Événements web", f"{ecommerce_total_events:,}")
            ecommerce_col2.metric("Visiteurs observés", f"{ecommerce_users:,}")
            ecommerce_col3.metric("Sessions observées", f"{ecommerce_sessions:,}")
            ecommerce_col4.metric("Pages suivies", f"{ecommerce_pages:,}")

            if "action" in ecommerce_usage.columns:
                action_summary = (
                    ecommerce_usage["action"]
                    .fillna("Non renseigné")
                    .astype(str)
                    .value_counts()
                    .reset_index()
                )
                action_summary.columns = ["Type d'action", "Événements"]

                st.markdown("**Répartition des actions web**")
                st.dataframe(
                    action_summary,
                    hide_index=True,
                    width="stretch",
                )

            if ecommerce_is_live:
                journey_preview = prepare_matomo_live_journey_preview(ecommerce_usage)

                st.markdown("**Aperçu des parcours visiteurs Matomo Live**")

                if journey_preview.empty:
                    st.info(
                        "Les données Matomo Live sont détectées, mais aucun parcours "
                        "visiteur exploitable n'a été trouvé dans les colonnes disponibles."
                    )
                else:
                    st.dataframe(
                        journey_preview,
                        hide_index=True,
                        width="stretch",
                    )

                st.info(
                    "Lecture : ces données proviennent des actionDetails détaillés "
                    "de Matomo. Elles permettent une analyse plus fine des parcours "
                    "visiteurs. Les limites métier restent toutefois les mêmes : "
                    "population éligible, mapping entité/campus et seuils d'adoption "
                    "ne sont pas encore disponibles."
                )
                
                st.markdown("**Recommandations Matomo Live**")
                render_recommendations(
                    [
                        "Analyser les parcours les plus fréquents pour identifier les pages d'entrée, "
                        "les pages critiques et les éventuels points de sortie.",
                        "Surveiller les pages produit les plus consultées afin de comprendre les centres "
                        "d'intérêt utilisateurs.",
                        "Vérifier le tunnel checkout pour détecter d'éventuels blocages ou abandons.",
                        "Compléter les données Matomo par un référentiel métier pour distinguer simple navigation "
                        "et adoption réelle.",
                    ]
                )
            elif ecommerce_has_matomo:
                st.info(
                    "Limite actuelle : les données Matomo sont issues d'un export agrégé. "
                    "Pour obtenir de vrais parcours utilisateur, il faut utiliser "
                    "l'API Live.getLastVisitsDetails."
                )
                
                st.markdown("**Recommandations Matomo**")
                render_recommendations(
                    [
                        "Passer à l'extraction RAW via Live.getLastVisitsDetails pour reconstruire "
                        "les parcours visiteurs.",
                        "Utiliser les top pages agrégées pour identifier les sections les plus consultées.",
                        "Compléter l'analyse avec des objectifs de conversion et des actions métier.",
                    ]
                )

    # ── Données manquantes / Qualité des données ──────────────────────────────

    unified_data_quality = prepare_unified_data_quality_table(
        filtered_usage,
        dashboard_adoption_vm.departmental,
        web_logs_df=data.web_logs,
    )

    with st.container(border=True):
        dq_title_col, dq_interpretation_col = st.columns(
            [4, 1],
            vertical_alignment="center",
        )

        with dq_title_col:
            st.subheader("Qualité des données")

        data_quality_interpretation = prepare_data_quality_interpretation(
            unified_data_quality,
        )
        data_quality_interpretation = add_recommendations_to_insight(
            data_quality_interpretation,
            prepare_data_quality_recommendations(unified_data_quality),
        )

        with dq_interpretation_col:
            with st.popover("💡 Interprétation IA"):
                render_interpretation_popover(data_quality_interpretation)

        st.caption(
            "Cette section distingue les indicateurs calculables avec les données actuelles "
            "des informations nécessaires pour mesurer une adoption métier complète."
        )

        if unified_data_quality.empty:
            st.info("Aucune information disponible sur la qualité des données.")
        else:
            services_count = unified_data_quality["Service"].nunique()

            services_with_missing_data = (
                unified_data_quality["Statut global"]
                .astype(str)
                .isin(["Partiel", "À compléter"])
                .sum()
            )

            with st.container(horizontal=True):
                st.metric("Services analysés", services_count, border=True)
                st.metric("Taux d’utilisation", "Non calculable", border=True)
                st.metric(
                    "Services avec données manquantes",
                    int(services_with_missing_data),
                    border=True,
                )
            
            st.dataframe(
                unified_data_quality,
                hide_index=True,
                width="stretch",
                column_config={
                    "Événements disponibles": st.column_config.NumberColumn(
                        "Événements disponibles",
                        format="%d",
                    ),
                    "Utilisateurs actifs observés": st.column_config.NumberColumn(
                        "Utilisateurs actifs observés",
                        format="%d",
                    ),
                },
            )

            st.markdown(
                """
                <div class="data-quality-card">
                    <strong>Méthodologie</strong><br>
                    Le taux d’utilisation réel nécessite une population éligible par service. 
                    L’adoption par entité ou campus nécessite aussi un mapping utilisateur vers organisation.
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("### Demandez à Adoption AI")
    st.text_input("Posez votre question sur l'adoption...", key="adoption_ai_question")

# ── Onglet Learning Center ─────────────────────────────────────────────────────

if selected_tab == "Learning Center":
    lc_vm = dashboard_service.get_learning_center_view()
    lc_display_kpis = lc_vm.latest_kpis.copy()

    if not lc_vm.daily_trend.empty:
        latest_trend = lc_vm.daily_trend.sort_values("date").iloc[-1]
        lc_display_kpis["dau"] = int(latest_trend["dau"])
        lc_display_kpis["wau"] = int(latest_trend["wau"])
        lc_display_kpis["mau"] = int(latest_trend["mau"])
    st.subheader("Learning Center website")
    

    with st.container(horizontal=True):
        st.metric("DAU", f"{lc_display_kpis['dau']:,}", border=True)
        st.metric("WAU", f"{lc_display_kpis['wau']:,}", border=True)
        st.metric("MAU", f"{lc_display_kpis['mau']:,}", border=True)
        st.metric("Taux d'erreur", f"{lc_display_kpis['error_rate']:.2%}", border=True)

        
    if not lc_vm.daily_kpis.empty:
        with st.container(border=True):
            st.subheader("Tendance d'adoption")
            st.line_chart(
                lc_vm.daily_trend,
                x="date",
                y=["dau", "wau", "mau"],
            )
        
        request_cols = [
            "date",
            "total_requests",
            "human_requests",
            "page_views",
            "api_requests",
            "errors_4xx",
            "errors_5xx",
        ]

        traffic_labels = {
            "total_requests": "Requêtes totales",
            "human_requests": "Requêtes utilisateurs",
            "page_views": "Pages vues",
            "api_requests": "Appels API",
            "errors_4xx": "Erreurs client 4xx",
            "errors_5xx": "Erreurs serveur 5xx",
        }

        traffic_df = lc_vm.daily_kpis[request_cols].rename(columns=traffic_labels)

        with st.container(border=True):
            st.subheader("Trafic et erreurs techniques")
            st.line_chart(
                traffic_df,
                x="date",
                y=list(traffic_labels.values()),
            )
            
    else:
        st.info("Aucun `daily-kpis.csv` Learning Center n'a été trouvé.")

    route_left, route_right = st.columns(2)
    with route_left:
        with st.container(border=True):
            st.subheader("Pages / routes les plus consultées")
            st.dataframe(lc_vm.top_routes.head(25), hide_index=True)
    with route_right:
        with st.container(border=True):
            st.subheader("Répartition par type de route")
            if not lc_vm.route_summary.empty:
                st.bar_chart(lc_vm.route_summary, x="route_type", y="requests")
            else:
                st.info("Aucun `top-routes.csv` disponible.")


# ── Onglet Adoption détaillée ─────────────────────────────────────────────────

if selected_tab == "Adoption détaillée":
    adoption_vm = dashboard_service.get_adoption_view(filtered_usage)
    st.subheader("Vue globale de l’adoption")
    st.caption(
        "Analyse multi-service basée sur les données filtrées : "
        "utilisateurs actifs, fréquence d’utilisation, activité par service "
        "et répartition par entité ou campus."
    )

    with st.container(horizontal=True):
        st.metric("DAU", f"{adoption_vm.metrics['dau']:,}", border=True)
        st.metric("WAU", f"{adoption_vm.metrics['wau']:,}", border=True)
        st.metric("MAU", f"{adoption_vm.metrics['mau']:,}", border=True)
        st.metric("Fréquence moyenne", f"{adoption_vm.metrics['avg_events_per_active_user']:.1f}", border=True)

    if not adoption_vm.timeseries.empty:
        with st.container(border=True):
            st.subheader("Activité par service")
            st.line_chart(adoption_vm.timeseries, x="date", y="active_users", color="service")

        with st.container(border=True):
            st.subheader("Usage par entité / campus")

            entity_usage = adoption_vm.departmental.copy()

            if not entity_usage.empty:
                entity_usage["department"] = entity_usage["department"].replace(
                    {"Unknown": "Non renseigné"}
                )

                entity_usage = entity_usage.rename(
                    columns={
                        "department": "Entité / campus",
                        "service": "Service",
                        "active_users": "Utilisateurs actifs",
                        "events": "Événements",
                        "avg_events_per_user": "Événements / utilisateur",
                        "share_of_active_users": "Part des utilisateurs actifs (%)",
                    }
                )

                st.dataframe(
                    entity_usage,
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Aucune donnée d’usage par entité ou campus disponible.")
    

    #with st.container(border=True):
     #   st.subheader("Utilisateurs inactifs")
      #  st.dataframe(adoption_vm.inactive, hide_index=True)

    #st.subheader("Synthèse hebdomadaire")
    #st.write(adoption_vm.weekly_summary)

    #for alert in adoption_vm.alerts:
     #   st.warning(alert)


# ── Onglet Security Analytics ─────────────────────────────────────────────────

if selected_tab == "Security Analytics":
    security_vm = SecurityService.analyze(data.web_logs)

    with st.container(horizontal=True):
        st.metric("Requêtes suspectes", f"{security_vm.total_suspicious:,}", border=True)
        st.metric("IP distinctes", f"{security_vm.summary['unique_ips']:,}", border=True)
        st.metric("Routes ciblées", f"{security_vm.summary['unique_routes']:,}", border=True)
        st.metric("Erreurs 4xx/5xx", f"{security_vm.summary['error_events']:,}", border=True)

    if not security_vm.top_routes.empty:
        with st.container(border=True):
            st.subheader("Routes suspectes les plus ciblées")
            st.bar_chart(security_vm.top_routes, x="route", y="requests")

        with st.container(border=True):
            st.subheader("IP sources les plus actives")
            st.dataframe(security_vm.top_ips, hide_index=True)
    else:
        st.info("Aucune route suspecte détectée dans l'échantillon `nginx-events.csv` configuré.")

    with st.container(border=True):
        st.subheader("Événements suspects")
        st.dataframe(security_vm.suspicious_events.head(1000), hide_index=True)


# ── Onglet Booking ────────────────────────────────────────────────────────────

if selected_tab == "Booking":
    st.header("Booking")

    booking_usage = data.usage_events[
        data.usage_events["service"] == "Booking"
    ].copy()

    booking_daily = data.raw_by_source.get(
        "booking",
        {},
    ).get(
        "daily_kpis",
        pd.DataFrame(),
    ).copy()

    if booking_usage.empty and booking_daily.empty:
        st.info(
            "Aucune donnée Booking n’est disponible pour le moment. "
            "Ajoutez les fichiers dans `data/um6p/booking/` puis relancez l’application."
        )
    else:
        st.caption(
            "KPI d’adoption Booking calculés à partir des événements d’usage "
            "et des KPI quotidiens anonymisés."
        )

        if not booking_daily.empty:
            booking_daily["date"] = pd.to_datetime(
                booking_daily["date"],
                errors="coerce",
            )
            booking_daily = booking_daily.dropna(subset=["date"]).sort_values("date")

            last_kpis = booking_daily.iloc[-1]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("DAU", f"{int(last_kpis['dau']):,}")
            col2.metric("WAU", f"{int(last_kpis['wau']):,}")
            col3.metric("MAU", f"{int(last_kpis['mau']):,}")
            col4.metric("Événements du dernier jour", f"{int(last_kpis['activity_events']):,}")
            st.subheader("Évolution des KPI Booking")

            booking_trend = prepare_daily_trend(booking_daily)

            if not booking_trend.empty:
                fig = px.line(
                    booking_trend,
                    x="date",
                    y=["dau", "wau", "mau"],
                    markers=True,
                    title="Évolution DAU / WAU / MAU - Booking",
                )
                st.plotly_chart(fig, width="stretch")
            else:
                st.warning("Aucune tendance Booking disponible.")
        else:
            st.warning(
                "Les KPI quotidiens Booking ne sont pas disponibles. "
                "Les métriques seront calculées uniquement depuis les événements d’usage."
            )

            metrics = AdoptionMetricsService.compute(booking_usage)

            col1, col2, col3 = st.columns(3)
            col1.metric("DAU", f"{metrics['dau']:,}")
            col2.metric("WAU", f"{metrics['wau']:,}")
            col3.metric("MAU", f"{metrics['mau']:,}")

        st.subheader("Fréquence d’utilisation")

        frequency = compute_usage_frequency(booking_usage)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Utilisateurs actifs", f"{frequency['active_users']:,}")
        col2.metric("Événements totaux", f"{frequency['total_events']:,}")
        col3.metric(
            "Événements / utilisateur",
            f"{frequency['avg_events_per_active_user']:.2f}",
        )
        col4.metric(
            "Jours actifs / utilisateur",
            f"{frequency['avg_active_days_per_user']:.2f}",
        )

        st.subheader("Activité par action")

        if not booking_usage.empty:
            action_summary = (
                booking_usage.groupby("action", as_index=False)
                .agg(
                    events=("user_id", "size"),
                    active_users=("user_id", "nunique"),
                )
                .sort_values("events", ascending=False)
                .head(15)
            )

            fig_actions = px.bar(
                action_summary,
                x="action",
                y="events",
                title="Top actions Booking",
            )
            st.plotly_chart(fig_actions, width="stretch")

            st.subheader("Usage par entité / campus")

            booking_breakdown = departmental_breakdown(booking_usage).head(10)
            st.dataframe(booking_breakdown, width="stretch")
        else:
            st.info("Aucun événement d’usage Booking disponible.")


# ── Onglet Assistant IA ───────────────────────────────────────────────────────

if selected_tab == "Assistant IA":
    st.subheader("Assistant IA d’adoption")
    assistant = get_assistant()
    

    if "assistant_chat_history" not in st.session_state:
        st.session_state.assistant_chat_history = [
            {
                "role": "assistant",
                "content": (
                    "Bonjour, je peux répondre aux questions sur les KPI "
                    "d’adoption : DAU, WAU, MAU, évolution, fréquence "
                    "d’utilisation, services sous-utilisés et routes suspectes."
                ),
            }
        ]

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("Posez une question sur les données filtrées dans le dashboard.")

    with col2:
        if st.button("Nouvelle conversation"):
            st.session_state.assistant_chat_history = [
                {
                    "role": "assistant",
                    "content": (
                        "Nouvelle conversation démarrée. "
                        "Quelle analyse souhaitez-vous effectuer ?"
                    ),
                }
            ]
            st.rerun()

    for message in st.session_state.assistant_chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Posez votre question sur les KPI d’adoption..."
    )

    if question:
        st.session_state.assistant_chat_history.append(
            {
                "role": "user",
                "content": question,
            }
        )

        source_key_by_service = {
            "Learning Center": "learning_center",
            "Booking": "booking",
        }

        if isinstance(selected_services, str):
            selected_service_list = [selected_services]
        else:
            selected_service_list = list(selected_services)

        if len(selected_service_list) == 1:
            selected_source_key = source_key_by_service.get(
                selected_service_list[0]
            )
        else:
            selected_source_key = None

        if selected_source_key is not None:
            selected_daily_kpis = data.raw_by_source.get(
                selected_source_key,
                {},
            ).get(
                "daily_kpis",
                pd.DataFrame(),
            )
        else:
            selected_daily_kpis = pd.DataFrame()

        with st.spinner("Analyse en cours..."):
            response = assistant.answer(
                question,
                context={
                    "usage_df": filtered_usage,
                    "web_logs_df": data.web_logs,
                    "daily_kpis": selected_daily_kpis,
                },
            )

        st.session_state.assistant_chat_history.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        st.rerun()
# ── Onglet Architecture ───────────────────────────────────────────────────────


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
)


# ── Configuration de la page ───────────────────────────────────────────────────

st.set_page_config(page_title="AI Adoption Analytics", layout="wide")


# ── Chargement des données (mis en cache par session) ─────────────────────────

@st.cache_resource(show_spinner="Chargement des données...")
def load_data():
    service = DashboardService()
    data = service.load()
    return service, data


dashboard_service, data = load_data()

def build_unified_adoption_trend(usage_df: pd.DataFrame) -> pd.DataFrame:
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

        date_range = pd.date_range(
            service_df["date"].min(),
            service_df["date"].max(),
            freq="D",
        )

        for current_date in date_range:
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

def classify_interaction_type(service: str, interaction: str) -> str:
    """Classe une interaction dans une catégorie commune."""

    service_text = str(service).lower()
    interaction_text = str(interaction).lower()

    if "booking" in service_text:
        return "Action métier"

    if interaction_text.startswith("/api") or "/api/" in interaction_text:
        return "API"

    if interaction_text.startswith("/") or interaction_text.startswith("http"):
        return "Page / route"

    if "matomo" in service_text:
        return "Événement web"

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

    # Booking : actions métier depuis les événements normalisés
    if "action" in usage_df.columns:
        booking_events = usage_df[
            usage_df["service"].astype(str).str.lower().eq("booking")
        ].copy()

        if not booking_events.empty:
            booking_events["interaction"] = (
                booking_events["action"]
                .fillna("Non renseigné")
                .astype(str)
                .replace({"": "Non renseigné", "Unknown": "Non renseigné"})
            )

            booking_grouped = (
                booking_events.groupby("interaction")
                .size()
                .reset_index(name="events")
            )

            booking_total = booking_grouped["events"].sum()

            for _, row in booking_grouped.iterrows():
                interaction = row["interaction"]
                events = int(row["events"])

                rows.append(
                    {
                        "Service": "Booking",
                        "Type d’interaction": classify_interaction_type(
                            "Booking",
                            interaction,
                        ),
                        "Interaction": interaction,
                        "Événements": events,
                        "Part des événements (%)": round(
                            events / booking_total * 100,
                            2,
                        )
                        if booking_total
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
            if "action" in service_usage.columns:
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

    observation = (
        f"Les KPI affichés couvrent {service_scope}. "
        f"Ils indiquent {dau:,} utilisateurs actifs quotidiens, "
        f"{wau:,} utilisateurs actifs hebdomadaires, "
        f"{mau:,} utilisateurs actifs mensuels et une fréquence moyenne de "
        f"{frequency:.1f} événements par utilisateur actif."
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
        "Interprétation contrôlée basée sur les KPI calculés par le moteur Python."
    )

    st.markdown("**Observation**")
    st.write(insight["observation"])

    st.markdown("**Interprétation**")
    st.write(insight["interpretation"])

    st.markdown("**Recommandation**")
    st.write(insight["recommendation"])

# ── Sidebar — sources & filtres ────────────────────────────────────────────────
if st.sidebar.button("Rafraîchir les données"):
    load_data.clear()
    st.rerun()

with st.sidebar:
    st.header("Filtres")
    filter_opts = dashboard_service.get_filter_options(data.usage_events)
    selected_services = st.multiselect(
        "Services", filter_opts["services"], default=filter_opts["services"]
    )
    selected_departments = st.multiselect(
        "Entités / campus", filter_opts["departments"], default=filter_opts["departments"]
    )

filtered_usage = DashboardService.apply_filters(
    data.usage_events, selected_services, selected_departments
)

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

    if selected_service != "Tous" and "service" in working_df.columns:
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

    if selected_service == "Tous":
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

# ── Onglets ────────────────────────────────────────────────────────────────────

dashboard_tab,learning_center_tab, adoption_tab, security_tab, booking_tab, assistant_tab = st.tabs(
    ["Dashboard adoption","Learning Center", "Adoption détaillée", "Security Analytics", "Booking", "Assistant IA"]
)

# ── Onglet Dashboard adoption unifié ───────────────────────────────────────────

with dashboard_tab:
    st.subheader("Dashboard adoption unifié")
    st.caption(
        "Vue centrale multi-application basée sur un modèle commun de données. "
        "Les services sont analysés avec la même structure afin d'assurer une expérience cohérente."
    )

    dashboard_adoption_vm = dashboard_service.get_adoption_view(filtered_usage)

    st.markdown(
        """
        **Principe :** chaque application est affichée avec les mêmes champs et les mêmes KPI.  
        Lorsqu'une donnée n'est pas disponible pour un service, elle est indiquée comme **Non renseigné** ou **Non calculable**.
        """
    )

    kpi_interpretation = prepare_kpi_interpretation(
        dashboard_adoption_vm.metrics,
        filtered_usage,
    )

    kpi_title_col, kpi_popover_col = st.columns(
        [4, 1],
        vertical_alignment="center",
    )

    with kpi_title_col:
        st.subheader("Vue d’ensemble KPI")

    with kpi_popover_col:
        with st.popover("💡 Interprétation IA"):
            render_interpretation_popover(kpi_interpretation)

    with st.container(horizontal=True):
        st.metric("DAU", f"{dashboard_adoption_vm.metrics['dau']:,}", border=True)
        st.metric("WAU", f"{dashboard_adoption_vm.metrics['wau']:,}", border=True)
        st.metric("MAU", f"{dashboard_adoption_vm.metrics['mau']:,}", border=True)
        st.metric(
            "Fréquence moyenne",
            f"{dashboard_adoption_vm.metrics['avg_events_per_active_user']:.1f}",
            border=True,
        )

    st.info(
        "Le taux d’utilisation réel nécessite la population éligible par service. "
        "Cette donnée n’est pas disponible actuellement, donc le taux reste non calculable."
    )

    # ── Évolution de l’adoption ────────────────────────────────────────────────

    unified_trend = build_unified_adoption_trend(filtered_usage)

    with st.container(border=True):
        if unified_trend.empty:
            st.subheader("Évolution de l’adoption")
            st.info("Aucune donnée disponible pour afficher l’évolution de l’adoption.")
        else:
            available_services = sorted(
                unified_trend["service"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            kpi_mapping = {
                "DAU": "dau",
                "WAU": "wau",
                "MAU": "mau",
                "Événements": "events",
                "Fréquence": "frequency",
            }

            evolution_title_col, metric_popover_col, interpretation_popover_col = st.columns(
                [3, 1, 1],
                vertical_alignment="center",
            )

            with evolution_title_col:
                st.subheader("Évolution de l’adoption")

            with metric_popover_col:
                with st.popover("Choisir métriques"):
                    selected_service = st.selectbox(
                        "Service",
                        ["Tous les services", *available_services],
                        key="unified_trend_service",
                    )

                    selected_metric_label = st.selectbox(
                        "KPI",
                        list(kpi_mapping.keys()),
                        key="unified_trend_kpi",
                    )

            selected_kpi = kpi_mapping[selected_metric_label]

            evolution_interpretation = prepare_evolution_interpretation(
                unified_trend,
                selected_service,
                selected_metric_label,
                selected_kpi,
            )

            with interpretation_popover_col:
                with st.popover("💡 Interprétation IA"):
                    render_interpretation_popover(evolution_interpretation)

            trend_to_display = unified_trend.copy()

            if selected_service != "Tous les services":
                trend_to_display = trend_to_display[
                    trend_to_display["service"] == selected_service
                ]

            chart = (
                alt.Chart(trend_to_display)
                .mark_line(strokeWidth=2.5)
                .encode(
                    x=alt.X("date:T", title=""),
                    y=alt.Y(f"{selected_kpi}:Q", title=selected_kpi),
                    color=alt.Color(
                        "service:N",
                        title=None,
                        scale=alt.Scale(
                            domain=["Booking", "Learning Center"],
                            range=["#1f77d0", "#ff8a00"],
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            direction="horizontal",
                            labelFontSize=14,
                            symbolSize=120,
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("service:N", title="Service"),
                        alt.Tooltip(f"{selected_kpi}:Q", title=selected_metric_label),
                    ],
                )
                .properties(height=360)
            )

            st.altair_chart(chart, use_container_width=True)
    # ── Usage par entité / campus ──────────────────────────────────────────────

    unified_entity_usage = prepare_unified_entity_usage_table(
        dashboard_adoption_vm.departmental
    )

    with st.container(border=True):
        st.subheader("Usage par entité / campus")

        entity_usage_interpretation = prepare_entity_usage_interpretation(
            unified_entity_usage,
        )

        with st.popover("💡 Interprétation IA"):
            render_interpretation_popover(entity_usage_interpretation)

        st.caption(
            "Table commune appliquée à tous les services. "
            "Les champs indisponibles restent visibles afin de distinguer les données calculées "
            "des données manquantes."
        )

        if unified_entity_usage.empty:
            st.info("Aucune donnée disponible pour l’usage par entité ou campus.")
        else:
            st.dataframe(
                unified_entity_usage,
                hide_index=True,
                use_container_width=True,
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
    # ── Top interactions ──────────────────────────────────────────────────────

    unified_top_interactions = prepare_unified_top_interactions_table(
        filtered_usage,
        web_logs_df=data.web_logs,
        top_n=15,
    )

    with st.container(border=True):
        st.subheader("Top interactions")

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
                use_container_width=True,
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

    # ── Données manquantes / Qualité des données ──────────────────────────────

    unified_data_quality = prepare_unified_data_quality_table(
        filtered_usage,
        dashboard_adoption_vm.departmental,
        web_logs_df=data.web_logs,
    )

    with st.container(border=True):
        st.subheader("Données manquantes / Qualité des données")

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
                use_container_width=True,
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

            st.info(
                "Le taux d’utilisation réel nécessite une population éligible par service. "
                "L’adoption par entité ou campus nécessite aussi un mapping utilisateur vers organisation."
            )

# ── Onglet Learning Center ─────────────────────────────────────────────────────

with learning_center_tab:
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

with adoption_tab:
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

with security_tab:
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

with booking_tab:
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

with assistant_tab:
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


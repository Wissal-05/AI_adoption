"""AI Adoption Analytics — Interface Streamlit.

Ce fichier est la couche UI pure. Il ne contient aucune logique métier :
tous les calculs et traitements sont délégués aux services.

Architecture :
  app.py → services/ → metrics/ + reporting/ + ai/ → data_sources/ → schemas/
"""

from pathlib import Path
import sys
import pandas as pd

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.services.security_service import SecurityService
from adoption_analytics.services.data_freshness import DataFreshnessService
from adoption_analytics.ai import get_assistant


# ── Configuration de la page ───────────────────────────────────────────────────

st.set_page_config(page_title="AI Adoption Analytics", layout="wide")


# ── Chargement des données (mis en cache par session) ─────────────────────────

@st.cache_data(show_spinner="Chargement des sources de données...")
def load_data():
    service = DashboardService()
    data = service.load()
    return service, data


dashboard_service, data = load_data()



# ── Sidebar — sources & filtres ────────────────────────────────────────────────

with st.sidebar:
    st.header("Sources")
    st.caption(f"Learning Center: `{data.learning_center_source_dir}`")
    if data.booking_available:
        st.caption("Booking: ✅ disponible")
    else:
        st.caption("Booking: ⏳ en attente d'accès")

    if data.available_sources:
        st.caption(f"Sources actives: {', '.join(data.available_sources)}")

    # ── Statut de fraîcheur des données ───────────────────────────────────────
    st.header("Fraîcheur des données")
    freshness_service = DataFreshnessService()
    for src in data.available_sources:
        report = freshness_service.get_freshness(src)
        st.caption(f"**{src.replace('_', ' ').title()}**")
        if report.status.startswith("À jour"):
            st.success(f"Statut : {report.status}\n\nÂge : {report.data_age_formatted}")
        else:
            st.warning(f"Statut : {report.status}\n\nÂge : {report.data_age_formatted}")
        if report.last_success_run:
            st.caption(f"Dernière ingestion : {report.last_success_run[:16].replace('T', ' ')}")

    st.header("Filtres")
    filter_opts = dashboard_service.get_filter_options(data.usage_events)
    selected_services = st.multiselect(
        "Services", filter_opts["services"], default=filter_opts["services"]
    )
    selected_departments = st.multiselect(
        "Départements", filter_opts["departments"], default=filter_opts["departments"]
    )

filtered_usage = DashboardService.apply_filters(
    data.usage_events, selected_services, selected_departments
)


# ── Onglets ────────────────────────────────────────────────────────────────────

learning_center_tab, adoption_tab, security_tab, booking_tab, assistant_tab, architecture_tab = st.tabs(
    ["Learning Center", "Adoption détaillée", "Security Analytics", "Booking", "Assistant IA", "Architecture"]
)


# ── Onglet Learning Center ─────────────────────────────────────────────────────

with learning_center_tab:
    lc_vm = dashboard_service.get_learning_center_view()
    st.subheader("Learning Center website")
    st.caption(
        "KPI d’adoption calculés depuis `nginx-events.csv`. "
        "Trafic et erreurs issus de `daily-kpis.csv` et `top-routes.csv`."
    )

    with st.container(horizontal=True):
        st.metric("DAU", f"{lc_vm.latest_kpis['dau']:,}", border=True)
        st.metric("WAU", f"{lc_vm.latest_kpis['wau']:,}", border=True)
        st.metric("MAU", f"{lc_vm.latest_kpis['mau']:,}", border=True)
        st.metric("Taux d'erreur", f"{lc_vm.latest_kpis['error_rate']:.2%}", border=True)

    if not lc_vm.daily_kpis.empty:
        with st.container(border=True):
            st.subheader("Tendance d'adoption")
            st.line_chart(
                lc_vm.daily_trend,
                x="date",
                y=["dau", "wau", "mau"],
            )
        request_cols = ["date", "total_requests", "human_requests", "page_views",
                        "api_requests", "errors_4xx", "errors_5xx"]
        with st.container(border=True):
            st.subheader("Requêtes et erreurs")
            st.line_chart(lc_vm.daily_kpis[request_cols], x="date", y=request_cols[1:])
    else:
        st.info("Aucun `daily-kpis.csv` Learning Center n'a été trouvé.")

    route_left, route_right = st.columns(2)
    with route_left:
        with st.container(border=True):
            st.subheader("Top routes")
            st.dataframe(lc_vm.top_routes.head(25), hide_index=True)
    with route_right:
        with st.container(border=True):
            st.subheader("Types de routes")
            if not lc_vm.route_summary.empty:
                st.bar_chart(lc_vm.route_summary, x="route_type", y="requests")
            else:
                st.info("Aucun `top-routes.csv` disponible.")


# ── Onglet Adoption détaillée ─────────────────────────────────────────────────

with adoption_tab:
    adoption_vm = dashboard_service.get_adoption_view(filtered_usage)

    with st.container(horizontal=True):
        st.metric("DAU", f"{adoption_vm.metrics['dau']:,}", border=True)
        st.metric("WAU", f"{adoption_vm.metrics['wau']:,}", border=True)
        st.metric("MAU", f"{adoption_vm.metrics['mau']:,}", border=True)
        st.metric("Fréquence moyenne", f"{adoption_vm.metrics['avg_events_per_active_user']:.1f}", border=True)

    if not adoption_vm.timeseries.empty:
        with st.container(border=True):
            st.subheader("Activité par service")
            st.line_chart(adoption_vm.timeseries, x="date", y="active_users", color="service")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Usage par département")
            st.dataframe(adoption_vm.departmental, hide_index=True)
    with right:
        with st.container(border=True):
            st.subheader("Services sous-utilisés")
            st.dataframe(adoption_vm.underused, hide_index=True)

    with st.container(border=True):
        st.subheader("Utilisateurs inactifs")
        st.dataframe(adoption_vm.inactive, hide_index=True)

    st.subheader("Synthèse hebdomadaire")
    st.write(adoption_vm.weekly_summary)

    for alert in adoption_vm.alerts:
        st.warning(alert)


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
    st.subheader("Booking")
    st.info(
        "La source Booking est réservée dans le dépôt, mais aucun fichier n'est chargé pour le moment. "
        "Ajoutez les futurs fichiers dans `data/um6p/booking/` puis branchez un connecteur dédié."
    )


# ── Onglet Assistant IA ───────────────────────────────────────────────────────

with assistant_tab:
    st.subheader("Questions en langage naturel")
    assistant = get_assistant()
    st.caption(f"Moteur actif : `{assistant}`")

    question = st.text_input(
        "Question",
        placeholder="Ex: Quelles routes suspectes ont été détectées sur Learning Center ?",
    )
    if question:
        response = assistant.answer(
            question,
            context={
                "usage_df": filtered_usage,
                "web_logs_df": data.web_logs,
                "daily_kpis": data.learning_center_daily,
            }
        )
        st.markdown(response)


# ── Onglet Architecture ───────────────────────────────────────────────────────

with architecture_tab:
    st.subheader("Architecture logicielle")
    st.markdown(
        """
        ### Couches (de l'UI vers l'infrastructure)

        | Couche | Module | Rôle |
        |---|---|---|
        | UI | `app.py` | Affichage Streamlit uniquement, aucune logique métier |
        | Application | `services/` | Orchestration : données → métriques → ViewModels |
        | Domaine | `metrics/`, `reporting/`, `ai/` | Calculs, rapports, assistant IA |
        | Infrastructure | `data_sources/` | Connecteurs CSV, normalisation vers schémas canoniques |
        | Configuration | `config/settings.py` | Pydantic-settings, aucun chemin hardcodé |
        | Schémas | `schemas/` | Contrats de données UsageEvent et WebLog |

        ### Ajouter une nouvelle source

        1. Créer `src/adoption_analytics/data_sources/<nom>/connector.py`
        2. Hériter de `DataSource`, implémenter `load()` → retourner un DataFrame conforme au schéma
        3. Déclarer dans `data_sources/registry.py` ou utiliser `@register_source("nom")`
        4. Les métriques, rapports, alertes et l'assistant deviennent immédiatement disponibles

        ### Changer le moteur d'assistant

        Définir `ASSISTANT_ENGINE=llm` dans `.env` et configurer `OPENAI_API_KEY`.
        """
    )

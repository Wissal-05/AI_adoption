"""AI Adoption Analytics — Interface Streamlit.

Ce fichier est la couche UI pure. Il ne contient aucune logique métier :
tous les calculs et traitements sont délégués aux services.

Architecture :
  app.py → services/ → metrics/ + reporting/ + ai/ → data_sources/ → schemas/
"""

from pathlib import Path
import sys
import pandas as pd
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



# ── Sidebar — sources & filtres ────────────────────────────────────────────────
if st.sidebar.button("Rafraîchir les données"):
    load_data.clear()
    st.rerun()

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
    st.caption(f"Moteur actif : `{assistant}`")

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



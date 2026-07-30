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
        st.subheader("Évolution de l’adoption")

        if unified_trend.empty:
            st.info("Aucune donnée disponible pour afficher l’évolution de l’adoption.")
        else:
            available_services = sorted(
                unified_trend["service"].dropna().unique().tolist()
            )

            kpi_mapping = {
                "DAU": "dau",
                "WAU": "wau",
                "MAU": "mau",
                "Événements": "events",
                "Fréquence": "frequency",
            }

            selected_service = st.session_state.get(
                "unified_trend_service",
                "Tous les services",
            )
            selected_metric = st.session_state.get(
                "unified_trend_kpi",
                "DAU",
            )

            if selected_service not in ["Tous les services", *available_services]:
                selected_service = "Tous les services"

            if selected_metric not in kpi_mapping:
                selected_metric = "DAU"

            selected_kpi = kpi_mapping[selected_metric]

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
                        alt.Tooltip(f"{selected_kpi}:Q", title=selected_metric),
                    ],
                )
                .properties(height=360)
            )

            st.altair_chart(chart, use_container_width=True)

            with st.popover("Choisir métriques"):
                st.selectbox(
                    "Service",
                    ["Tous les services", *available_services],
                    key="unified_trend_service",
                )

                st.selectbox(
                    "KPI",
                    ["DAU", "WAU", "MAU", "Événements", "Fréquence"],
                    key="unified_trend_kpi",
                )

    # ── Usage par entité / campus ──────────────────────────────────────────────

    unified_entity_usage = prepare_unified_entity_usage_table(
        dashboard_adoption_vm.departmental
    )

    with st.container(border=True):
        st.subheader("Usage par entité / campus")

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


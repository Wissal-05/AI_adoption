"""Registre des outils pour le Tool Calling.

Cette couche est déterministe, indépendante de l'UI et de tout fournisseur LLM.
Elle expose des outils Python documentés sous un schéma JSON, prêts à être
branchés sur un moteur LLM.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import pandas as pd
from adoption_analytics.metrics.interactions import compute_top_interactions
from adoption_analytics.metrics.trends import build_unified_adoption_trend
from adoption_analytics.metrics.adoption import departmental_breakdown

from adoption_analytics.services.dashboard_service import DashboardService
from adoption_analytics.services.adoption_metrics_service import AdoptionMetricsService

@dataclass
class ToolResult:
    status: str  # 'success', 'partial', 'not_available', 'invalid_request', 'error'
    tool: str
    service: Optional[str]
    data: Dict[str, Any]
    message: Optional[str] = None
    limitations: List[str] = field(default_factory=list)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    callable: Callable[..., ToolResult]


class ToolRegistry:
    def __init__(self, dashboard_service: DashboardService):
        self.dashboard_service = dashboard_service
        self._tools: Dict[str, Tool] = {}

        # Enregistrer les outils
        self.register(Tool(
            name="get_usage_kpis",
            description="Récupère les KPIs d'usage globaux (DAU, WAU, MAU) pour un service donné.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Nom du service à analyser (ex: 'Booking', 'Learning Center', 'Ecommerce Demo')"
                    },
                    "reference_date": {
                        "type": ["string", "null"],
                        "description": "Date de référence optionnelle au format YYYY-MM-DD"
                    }
                },
                "required": ["service"]
            },
            callable=self.get_usage_kpis
        ))

        self.register(Tool(
            name="get_adoption_by_module",
            description="Récupère l'adoption par module pour un service donné.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking')"},
                    "module": {"type": ["string", "null"], "description": "Nom du module spécifique optionnel"},
                    "reference_date": {"type": ["string", "null"], "description": "Date de référence optionnelle au format YYYY-MM-DD"},
                    "window_days": {"type": "integer", "description": "Fenêtre de jours (défaut 30)"}
                },
                "required": ["service"]
            },
            callable=self.get_adoption_by_module
        ))

        self.register(Tool(
            name="get_adoption_by_campus",
            description="Récupère l'adoption par campus pour un module donné d'un service.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking')"},
                    "module": {"type": "string", "description": "Nom du module (ex: 'Housing')"},
                    "campus": {"type": ["string", "null"], "description": "Nom du campus spécifique optionnel"},
                    "reference_date": {"type": ["string", "null"], "description": "Date de référence optionnelle au format YYYY-MM-DD"},
                    "window_days": {"type": "integer", "description": "Fenêtre de jours (défaut 30)"}
                },
                "required": ["service", "module"]
            },
            callable=self.get_adoption_by_campus
        ))

        self.register(Tool(
            name="get_top_interactions",
            description="Récupère les interactions (actions/pages) les plus fréquentes.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking', 'Learning Center')"},
                    "measure": {"type": "string", "description": "Mesure: 'reach' (utilisateurs/IP distincts) ou 'events' (événements observés). Défaut 'reach'."},
                    "limit": {"type": "integer", "description": "Nombre de résultats (max 50, défaut 10)"},
                    "start_date": {"type": ["string", "null"], "description": "Date de début optionnelle au format YYYY-MM-DD"},
                    "end_date": {"type": ["string", "null"], "description": "Date de fin optionnelle au format YYYY-MM-DD"}
                },
                "required": ["service"]
            },
            callable=self.get_top_interactions
        ))

        self.register(Tool(
            name="get_data_quality",
            description="Récupère les métriques de qualité de données et limites du service.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking')"}
                },
                "required": ["service"]
            },
            callable=self.get_data_quality
        ))

        self.register(Tool(
            name="get_usage_evolution",
            description="Récupère la série temporelle de l'évolution de l'usage (utilisateurs actifs ou volume d'événements) pour un service.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking', 'Learning Center')"},
                    "metric": {"type": "string", "description": "Métrique à analyser: 'active_users' (défaut) ou 'events'"},
                    "reference_date": {"type": ["string", "null"], "description": "Date de fin optionnelle au format YYYY-MM-DD"},
                    "window_days": {"type": "integer", "description": "Fenêtre de jours (défaut 30)"}
                },
                "required": ["service"]
            },
            callable=self.get_usage_evolution
        ))

        self.register(Tool(
            name="get_organization_usage",
            description="Récupère l'usage observé réparti par organisation (Entité/Campus/Département).",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service à analyser (ex: 'Booking')"},
                    "reference_date": {"type": ["string", "null"], "description": "Date de fin optionnelle au format YYYY-MM-DD"},
                    "window_days": {"type": "integer", "description": "Fenêtre de jours (défaut 30)"}
                },
                "required": ["service"]
            },
            callable=self.get_organization_usage
        ))



    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                status="error",
                tool=name,
                service=kwargs.get("service"),
                data={},
                message=f"Le tool '{name}' n'existe pas."
            )
        try:
            return tool.callable(**kwargs)
        except Exception as e:
            return ToolResult(
                status="error",
                tool=name,
                service=kwargs.get("service"),
                data={},
                message=f"Erreur d'exécution: {str(e)}"
            )

    def get_usage_kpis(self, service: str, reference_date: Optional[str] = None) -> ToolResult:
        tool_name = "get_usage_kpis"

        if not service:
            return ToolResult(
                status="invalid_request",
                tool=tool_name,
                service=service,
                data={},
                message="Le paramètre 'service' est requis."
            )

        service_lower = service.lower().strip()

        if service_lower in ["tous les services", "all", "*"]:
            return ToolResult(
                status="invalid_request",
                tool=tool_name,
                service=service,
                data={},
                message="DAU, WAU et MAU doivent être analysés service par service car les identités utilisateurs ne sont pas réconciliées entre les sources."
            )

        # Résolution du service
        available_services_map = {}
        # Assuming we can get available services from usage_events if loaded
        if hasattr(self.dashboard_service, "_data") and self.dashboard_service._data:
            usage_df = self.dashboard_service.data.usage_events
            if not usage_df.empty and "service" in usage_df.columns:
                unique_services = usage_df["service"].dropna().unique().tolist()
                for srv in unique_services:
                    available_services_map[str(srv).lower().strip()] = str(srv)

        # Hardcode fallback for known services if data not loaded or empty
        if not available_services_map:
            available_services_map = {
                "booking": "Booking",
                "learning center": "Learning Center",
                "ecommerce demo": "Ecommerce Demo"
            }

        resolved_service = available_services_map.get(service_lower)

        if not resolved_service:
            available = ", ".join(available_services_map.values())
            return ToolResult(
                status="invalid_request",
                tool=tool_name,
                service=service,
                data={},
                message=f"Service inconnu: '{service}'. Services disponibles: {available}"
            )

        ref_timestamp = None
        if reference_date:
            try:
                ref_timestamp = pd.to_datetime(reference_date)
            except ValueError:
                return ToolResult(
                    status="invalid_request",
                    tool=tool_name,
                    service=resolved_service,
                    data={},
                    message=f"Format de date invalide: '{reference_date}'. Format attendu: YYYY-MM-DD."
                )

        limitations = []

        if resolved_service == "Booking":
            extended = self.dashboard_service.get_service_extended_analytics(resolved_service, reference_date=ref_timestamp)
            usage = extended.usage if extended and extended.usage else {}

            dau = usage.get("dau", 0)
            wau = usage.get("wau", 0)
            mau = usage.get("mau", 0)

            avg_days = usage.get("avg_active_days_per_active_user_30d")

            if avg_days is not None:
                frequency = {
                    "value": float(avg_days),
                    "unit": "days",
                    "definition": "average_active_days_per_active_user_30d"
                }
            else:
                frequency = None

            return ToolResult(
                status="success",
                tool=tool_name,
                service=resolved_service,
                data={
                    "reference_date": reference_date,
                    "dau": dau,
                    "wau": wau,
                    "mau": mau,
                    "frequency": frequency
                }
            )
        else:
            # Pour les autres services, utiliser les métriques génériques
            # Le dashboard service n'a pas de méthode pour obtenir juste un kpi_usage, on filtre raw
            if hasattr(self.dashboard_service, "_data") and self.dashboard_service._data:
                usage_df = self.dashboard_service.data.usage_events
                service_usage = usage_df[usage_df["service"].astype(str) == resolved_service].copy()
            else:
                service_usage = pd.DataFrame()

            metrics = AdoptionMetricsService.compute(service_usage, reference_date=ref_timestamp)

            dau = metrics.get("dau", 0)
            wau = metrics.get("wau", 0)
            mau = metrics.get("mau", 0)

            limitations.append("Comparable usage frequency is not available for this service.")

            return ToolResult(
                status="success",
                tool=tool_name,
                service=resolved_service,
                data={
                    "reference_date": reference_date,
                    "dau": dau,
                    "wau": wau,
                    "mau": mau,
                    "frequency": None
                },
                limitations=limitations
            )


    def _resolve_service(self, service: str) -> str | None:
        if not service:
            return None
        service_lower = service.lower().strip()
        available_services_map = {}
        if hasattr(self.dashboard_service, "_data") and self.dashboard_service._data:
            usage_df = self.dashboard_service.data.usage_events
            if not usage_df.empty and "service" in usage_df.columns:
                unique_services = usage_df["service"].dropna().unique().tolist()
                for srv in unique_services:
                    available_services_map[str(srv).lower().strip()] = str(srv)

        if not available_services_map:
            available_services_map = {
                "booking": "Booking",
                "learning center": "Learning Center",
                "ecommerce demo": "Ecommerce Demo"
            }

        return available_services_map.get(service_lower)

    def _parse_date(self, date_str: str | None) -> pd.Timestamp | None:
        if date_str is None:
            return None
        return pd.to_datetime(date_str)

    def _handle_invalid_service(self, tool_name: str, service: str) -> ToolResult:
        service_lower = str(service).lower().strip()
        if service_lower in ["tous les services", "all", "*"]:
            return ToolResult(
                status="invalid_request",
                tool=tool_name,
                service=service,
                data={},
                message="Sélectionnez un service spécifique." if tool_name == "get_top_interactions" else "Opération non applicable globalement."
            )

        return ToolResult(
            status="invalid_request",
            tool=tool_name,
            service=service,
            data={},
            message=f"Service inconnu: '{service}'"
        )


    def get_adoption_by_module(self, service: str, module: str | None = None, reference_date: str | None = None, window_days: int = 30) -> ToolResult:
        tool_name = "get_adoption_by_module"

        if not service:
            return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Le paramètre 'service' est requis.")

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        if resolved_service != "Booking":
            return ToolResult(
                status="not_available",
                tool=tool_name,
                service=resolved_service,
                data={},
                message="L'adoption par module n'est pas disponible pour ce service."
            )

        try:
            ref_ts = self._parse_date(reference_date)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Format de date invalide.")

        extended = self.dashboard_service.get_service_extended_analytics(resolved_service, reference_date=ref_ts, window_days=window_days)
        modules_data = extended.adoption_by_module or []

        if module:
            target = module.lower().strip()
            filtered = []
            available_modules = []
            for m in modules_data:
                m_name = str(m.get("module", ""))
                available_modules.append(m_name)
                if m_name.lower().strip() == target:
                    filtered.append(m)

            if not filtered:
                return ToolResult(
                    status="invalid_request",
                    tool=tool_name,
                    service=resolved_service,
                    data={},
                    message=f"Module inconnu: '{module}'. Modules disponibles: {', '.join(available_modules)}"
                )
            modules_data = filtered

        # Nettoyage pour s'assurer que c'est JSON-serializable
        result_data = []
        for m in modules_data:
            item = {
                "module": m.get("module"),
                "active_users": int(m.get("active_users", 0)) if pd.notna(m.get("active_users")) else 0,
                "eligible_users": int(m.get("eligible_users", 0)) if pd.notna(m.get("eligible_users")) else None,
                "observed_adoption_rate": float(m.get("observed_adoption_rate")) if pd.notna(m.get("observed_adoption_rate")) else None,
                "status": m.get("status")
            }
            # Règles strictes:
            if item["status"] == "telemetry_unavailable":
                item["observed_adoption_rate"] = None
            elif item["status"] == "eligible_population_unavailable":
                item["observed_adoption_rate"] = None

            result_data.append(item)

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data={"reference_date": reference_date, "window_days": window_days, "modules": result_data}
        )


    def get_adoption_by_campus(self, service: str, module: str, campus: str | None = None, reference_date: str | None = None, window_days: int = 30) -> ToolResult:
        tool_name = "get_adoption_by_campus"

        if not service or not module:
            return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Paramètres 'service' et 'module' requis.")

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        if resolved_service != "Booking":
            return ToolResult(
                status="not_available",
                tool=tool_name,
                service=resolved_service,
                data={},
                message="L'adoption par campus n'est pas disponible pour ce service."
            )

        try:
            ref_ts = self._parse_date(reference_date)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Format de date invalide.")

        extended = self.dashboard_service.get_service_extended_analytics(resolved_service, reference_date=ref_ts, window_days=window_days)
        campus_data = extended.adoption_by_campus or []

        # Filtre sur le module
        target_mod = module.lower().strip()
        mod_campus = [c for c in campus_data if str(c.get("module", "")).lower().strip() == target_mod]

        if not mod_campus:
            return ToolResult(
                status="not_available",
                tool=tool_name,
                service=resolved_service,
                data={},
                message="Population éligible par campus non disponible pour ce module."
            )

        if campus:
            target_camp = campus.lower().strip()
            filtered = []
            available_campus = []
            for c in mod_campus:
                c_name = str(c.get("campus", ""))
                available_campus.append(c_name)
                if c_name.lower().strip() == target_camp:
                    filtered.append(c)

            if not filtered:
                return ToolResult(
                    status="invalid_request",
                    tool=tool_name,
                    service=resolved_service,
                    data={},
                    message=f"Campus inconnu: '{campus}'. Campus disponibles: {', '.join(available_campus)}"
                )
            mod_campus = filtered

        # Tri par observed_adoption_rate décroissant si status == available
        def sort_key(c):
            if c.get("status") == "available" and pd.notna(c.get("observed_adoption_rate")):
                return float(c.get("observed_adoption_rate"))
            return -1.0

        mod_campus.sort(key=sort_key, reverse=True)

        result_data = []
        for c in mod_campus:
            item = {
                "module": c.get("module"),
                "campus": c.get("campus"),
                "active_users": int(c.get("active_users", 0)) if pd.notna(c.get("active_users")) else 0,
                "eligible_users": int(c.get("eligible_users", 0)) if pd.notna(c.get("eligible_users")) else None,
                "observed_adoption_rate": float(c.get("observed_adoption_rate")) if pd.notna(c.get("observed_adoption_rate")) else None,
                "status": c.get("status")
            }
            if item["status"] == "telemetry_unavailable":
                item["observed_adoption_rate"] = None
            elif item["status"] == "eligible_population_unavailable":
                item["observed_adoption_rate"] = None

            result_data.append(item)

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data={"reference_date": reference_date, "window_days": window_days, "campus_list": result_data}
        )

    def get_top_interactions(self, service: str, measure: str = "reach", limit: int = 10, start_date: str | None = None, end_date: str | None = None) -> ToolResult:
        tool_name = "get_top_interactions"

        if not service: return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Le paramètre 'service' est requis.")

        service_lower = service.lower().strip()
        if service_lower in ["tous les services", "all", "*"]:
            return ToolResult(
                status="invalid_request", tool=tool_name, service=service, data={},
                message="Les interactions ont des sémantiques différentes selon les services. Sélectionnez un service."
            )

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        try:
            limit = int(limit)
            if limit < 1 or limit > 50: raise ValueError()
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Limit doit être entre 1 et 50.")

        try:
            start_ts = self._parse_date(start_date)
            end_ts = self._parse_date(end_date)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Format de date invalide.")

        measure_lower = str(measure).lower().strip()
        if measure_lower in ["users", "utilisateurs", "reach"]:
            target_col = "reach"
        elif measure_lower in ["volume", "events"]:
            target_col = "events"
        else:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Measure doit être 'reach' ou 'events'.")

        # Filtrage temporel existant du registre
        usage_df = self.dashboard_service.data.usage_events if hasattr(self.dashboard_service, "_data") and self.dashboard_service._data else pd.DataFrame()
        web_logs_df = self.dashboard_service.data.web_logs if hasattr(self.dashboard_service, "_data") and self.dashboard_service._data else pd.DataFrame()

        def filter_dates(df, ts_col):
            if df is None or df.empty or ts_col not in df.columns: return df
            if start_ts: df = df[df[ts_col] >= start_ts]
            if end_ts: df = df[df[ts_col] <= end_ts]
            return df

        usage_df = filter_dates(usage_df, "event_timestamp")
        web_logs_ts_col = "timestamp" if web_logs_df is not None and not web_logs_df.empty and "timestamp" in web_logs_df.columns else "event_timestamp"
        web_logs_df = filter_dates(web_logs_df, web_logs_ts_col)

        # Appel du helper PURE partagé
        grouped, reach_type, limitations = compute_top_interactions(
            usage_events_df=usage_df,
            web_logs_df=web_logs_df,
            service=resolved_service,
            measure=measure_lower,
            limit=limit
        )

        if grouped.empty:
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"interactions": []})

        results = []
        for _, row in grouped.iterrows():
            results.append({
                "interaction": str(row["interaction"]),
                "reach": int(row["reach"]),
                "reach_type": reach_type,
                "event_count": int(row["events"])
            })

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data={"interactions": results},
            limitations=limitations
        )


    def get_data_quality(self, service: str) -> ToolResult:
        tool_name = "get_data_quality"

        if not service: return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Le paramètre 'service' est requis.")

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        if resolved_service != "Booking":
            return ToolResult(
                status="not_available", tool=tool_name, service=resolved_service, data={},
                message="Les contrôles de qualité structurés ne sont pas encore disponibles pour ce service."
            )

        extended = self.dashboard_service.get_service_extended_analytics(resolved_service)
        dq = extended.data_quality or {}

        if not dq:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={}, message="Qualité des données non disponible.")

        unique_event_users = int(dq.get("unique_event_users", 0)) if pd.notna(dq.get("unique_event_users")) else 0
        missing_entity_active_users = int(dq.get("missing_entity_active_users", 0)) if pd.notna(dq.get("missing_entity_active_users")) else 0

        if unique_event_users > 0:
            entity_coverage_active_users = (unique_event_users - missing_entity_active_users) / unique_event_users * 100.0
        else:
            entity_coverage_active_users = 0.0

        repeated_share = float(dq.get("possible_repeated_event_share", 0)) if pd.notna(dq.get("possible_repeated_event_share")) else 0.0

        limitations = []
        if entity_coverage_active_users < 100:
            limitations.append("Mapping entité partiel. Certaines actions orphelines limitent l'analyse.")
        if repeated_share > 0:
            limitations.append("Signatures répétées possibles. Aucune déduplication automatique.")
        limitations.append("Absence d'event_id unique empêchant de confirmer des doublons.")

        data = {
            "event_rows": int(dq.get("event_rows", 0)) if pd.notna(dq.get("event_rows")) else 0,
            "unique_event_users": unique_event_users,
            "session_rows": int(dq.get("session_rows", 0)) if pd.notna(dq.get("session_rows")) else 0,
            "unique_session_users": int(dq.get("unique_session_users", 0)) if pd.notna(dq.get("unique_session_users")) else 0,
            "mapped_users": int(dq.get("mapped_users", 0)) if pd.notna(dq.get("mapped_users")) else 0,
            "event_user_mapping_coverage": float(dq.get("event_user_mapping_coverage", 0)) if pd.notna(dq.get("event_user_mapping_coverage")) else 0.0,
            "session_user_mapping_coverage": float(dq.get("session_user_mapping_coverage", 0)) if pd.notna(dq.get("session_user_mapping_coverage")) else 0.0,
            "event_timestamp_parse_failures": int(dq.get("event_timestamp_parse_failures", 0)) if pd.notna(dq.get("event_timestamp_parse_failures")) else 0,
            "session_created_at_parse_failures": int(dq.get("session_created_at_parse_failures", 0)) if pd.notna(dq.get("session_created_at_parse_failures")) else 0,
            "missing_entity_users": int(dq.get("missing_entity_users", 0)) if pd.notna(dq.get("missing_entity_users")) else 0,
            "missing_entity_active_users": missing_entity_active_users,
            "entity_coverage_active_users": entity_coverage_active_users,
            "possible_repeated_event_rows": int(dq.get("possible_repeated_event_rows", 0)) if pd.notna(dq.get("possible_repeated_event_rows")) else 0,
            "possible_repeated_event_share": repeated_share
        }

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data=data,
            limitations=limitations
        )

    def get_usage_evolution(self, service: str, metric: str = "active_users", reference_date: str | None = None, window_days: int = 30) -> ToolResult:
        tool_name = "get_usage_evolution"

        if not service: return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Le paramètre 'service' est requis.")

        service_lower = service.lower().strip()
        if service_lower in ["tous les services", "all", "*"]:
            return ToolResult(
                status="invalid_request", tool=tool_name, service=service, data={},
                message="L'évolution des utilisateurs doit être analysée service par service car les identités ne sont pas réconciliées entre les sources."
            )

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        metric_lower = metric.lower().strip()
        if metric_lower in ["active_users", "users", "dau"]:
            target_metric = "dau"
        elif metric_lower in ["events", "volume"]:
            target_metric = "events"
        else:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="metric invalide. Utilisez 'active_users' ou 'events'.")

        try:
            window_days = int(window_days)
            if window_days < 1 or window_days > 365: raise ValueError()
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="window_days doit être entre 1 et 365.")

        try:
            ref_ts = self._parse_date(reference_date)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Format de date invalide.")

        if not hasattr(self.dashboard_service, "_data") or not self.dashboard_service._data:
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"series": []})

        usage_df = self.dashboard_service.data.usage_events
        if usage_df.empty or "service" not in usage_df.columns:
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"series": []})

        service_usage = usage_df[usage_df["service"].astype(str).str.lower() == resolved_service.lower()].copy()
        if service_usage.empty:
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"series": []})

        actual_min = service_usage["event_timestamp"].min()
        actual_max = service_usage["event_timestamp"].max()
        service_bounds = {}
        if pd.notna(actual_min) and pd.notna(actual_max):
            service_bounds[resolved_service] = (actual_min.normalize(), actual_max.normalize())

        # Déterminer la période
        service_usage["event_timestamp"] = pd.to_datetime(service_usage["event_timestamp"], errors="coerce")
        actual_max = service_usage["event_timestamp"].max()
        if pd.isna(actual_max):
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"series": []})

        actual_max = actual_max.normalize()
        end_ts = ref_ts.normalize() if ref_ts else actual_max
        start_ts = end_ts - pd.Timedelta(days=window_days - 1)

        # Le filtrage global des events est géré par la fonction elle-même (via service_bounds et start_date/end_date).
        # Mais pour get_trend_warning_message, il lui faut le DataFrame filtré globalement sur la fenêtre.
        mask = (service_usage["event_timestamp"] >= start_ts) & (service_usage["event_timestamp"] <= end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
        filtered_usage = service_usage[mask].copy()

        trend_df = build_unified_adoption_trend(filtered_usage, start_date=start_ts, end_date=end_ts, service_bounds=service_bounds)

        if trend_df.empty:
            return ToolResult(status="success", tool=tool_name, service=resolved_service, data={"series": []})

        warning = self.dashboard_service.get_trend_warning_message(filtered_usage, resolved_service)
        limitations = []
        if warning: limitations.append(warning)
        if target_metric == "events" and resolved_service == "Booking":
            limitations.append("Le volume événementiel de Booking peut inclure des signatures répétées.")

        series_data = []
        for _, row in trend_df.iterrows():
            series_data.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "value": int(row[target_metric]) if pd.notna(row[target_metric]) else 0
            })

        coverage_start = trend_df["date"].min().strftime("%Y-%m-%d")
        coverage_end = trend_df["date"].max().strftime("%Y-%m-%d")

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data={
                "metric": target_metric,
                "period_start": start_ts.strftime("%Y-%m-%d"),
                "period_end": end_ts.strftime("%Y-%m-%d"),
                "coverage_start": coverage_start,
                "coverage_end": coverage_end,
                "observed_days": len(trend_df),
                "latest_value": series_data[-1]["value"] if series_data else 0,
                "series": series_data
            },
            limitations=limitations
        )

    def get_organization_usage(self, service: str, reference_date: str | None = None, window_days: int = 30) -> ToolResult:
        tool_name = "get_organization_usage"

        if not service: return ToolResult(status="invalid_request", tool=tool_name, service=service, data={}, message="Le paramètre 'service' est requis.")

        service_lower = service.lower().strip()
        if service_lower in ["tous les services", "all", "*"]:
            return ToolResult(
                status="invalid_request", tool=tool_name, service=service, data={},
                message="Les dimensions organisationnelles ne sont pas homogènes entre les services."
            )

        resolved_service = self._resolve_service(service)
        if not resolved_service:
            return self._handle_invalid_service(tool_name, service)

        if resolved_service in ["Learning Center", "Ecommerce Demo"]:
            return ToolResult(
                status="not_available", tool=tool_name, service=resolved_service, data={},
                message="Les données organisationnelles fiables ne sont pas disponibles pour ce service."
            )

        try:
            window_days = int(window_days)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="window_days doit être un entier.")

        try:
            ref_ts = self._parse_date(reference_date)
        except ValueError:
            return ToolResult(status="invalid_request", tool=tool_name, service=resolved_service, data={}, message="Format de date invalide.")

        if not hasattr(self.dashboard_service, "_data") or not self.dashboard_service._data:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        usage_df = self.dashboard_service.data.usage_events
        if usage_df.empty or "service" not in usage_df.columns:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        service_usage = usage_df[usage_df["service"].astype(str).str.lower() == resolved_service.lower()].copy()
        if service_usage.empty:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        service_usage["event_timestamp"] = pd.to_datetime(service_usage["event_timestamp"], errors="coerce")
        actual_max = service_usage["event_timestamp"].max()
        if pd.isna(actual_max):
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        actual_max = actual_max.normalize()
        end_ts = ref_ts.normalize() if ref_ts else actual_max
        start_ts = end_ts - pd.Timedelta(days=window_days - 1)

        mask = (service_usage["event_timestamp"] >= start_ts) & (service_usage["event_timestamp"] <= end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
        filtered_usage = service_usage[mask].copy()

        if filtered_usage.empty:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        # Fix column if needed for departmental_breakdown
        # Usage events have 'department' for Booking
        if "department" not in filtered_usage.columns:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        # Treat missing entity correctly as "Non renseigné"
        filtered_usage["department"] = filtered_usage["department"].fillna("Non renseigné").replace({"Unknown": "Non renseigné", "": "Non renseigné"})

        dept_df = departmental_breakdown(filtered_usage)

        if dept_df.empty:
            return ToolResult(status="not_available", tool=tool_name, service=resolved_service, data={})

        orgs = []
        for _, row in dept_df.iterrows():
            orgs.append({
                "organization": str(row["department"]),
                "active_users": int(row["active_users"]) if pd.notna(row["active_users"]) else 0,
                "events": int(row["events"]) if pd.notna(row["events"]) else 0,
                "share_of_active_users": float(row["share_of_active_users"]) if pd.notna(row["share_of_active_users"]) else 0.0
            })

        return ToolResult(
            status="success",
            tool=tool_name,
            service=resolved_service,
            data={
                "period_start": start_ts.strftime("%Y-%m-%d"),
                "period_end": end_ts.strftime("%Y-%m-%d"),
                "organizations": orgs
            }
        )

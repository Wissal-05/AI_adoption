"""Registre des outils pour le Tool Calling.

Cette couche est déterministe, indépendante de l'UI et de tout fournisseur LLM.
Elle expose des outils Python documentés sous un schéma JSON, prêts à être
branchés sur un moteur LLM.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import pandas as pd

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

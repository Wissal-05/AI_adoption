import json
from dataclasses import dataclass, asdict, field
from typing import Any

from groq import Groq

from config.settings import settings
from adoption_analytics.ai.tool_registry import ToolRegistry, ToolResult
from adoption_analytics.ai.knowledge_retriever import KnowledgeRetriever


@dataclass
class AssistantResponse:
    answer: str
    tool_calls: list[str]
    limitations: list[str]
    error: str | None = None
    knowledge_sources: list[dict] = field(default_factory=list)


SYSTEM_PROMPT = """Tu es Adoption AI, assistant d'analyse de l'adoption des services numériques de l'entreprise.

Règles obligatoires :
1. Pour toute valeur analytique actuelle ou chiffrée, utiliser les tools. Le contexte documentaire ne remplace jamais un tool.
2. Utiliser le contexte documentaire uniquement pour expliquer : définitions, méthodologie, services et limitations.
3. Ne jamais inventer une information absente à la fois des tools et du contexte documentaire.
4. Lorsque le contexte documentaire est insuffisant, le dire.
5. Respecter les limitations retournées par les tools.
6. None, not_available et telemetry_unavailable ne signifient pas 0.
7. Ne jamais créer un KPI global multi-service si le tool le refuse.
8. Répondre en français par défaut, en étant concis et orienté décision.
9. Les noms Housing, Transport, Catering, Access, Repair, Admin et Other désignent des modules du service Booking. Lorsqu'un utilisateur demande leur adoption sans préciser le service, utiliser Booking comme service.
10. Une demande portant sur le NOMBRE d'utilisateurs actifs sur 30 jours correspond au MAU et doit utiliser get_usage_kpis. Utiliser get_usage_evolution uniquement si l'utilisateur exprime explicitement une intention temporelle : évolution, tendance, variation, progression, baisse, hausse, courbe, historique.
11. MAU = fenêtre de 30 jours, pas un mois calendaire. Si on demande "ce mois-ci", réponds "sur les 30 derniers jours disponibles". Ne dis jamais "ce mois-ci = X" s'il s'agit du MAU glissant. Si on demande une période calendaire non gérée, explique la métrique disponible sans inventer.
12. Ne dis jamais que le DAU correspond à "24 heures". Utilise "utilisateurs actifs sur la journée de référence" ou "utilisateurs actifs quotidiens".
13. Ne présente aucune cause comme probable (ex: problème de communication, accessibilité, formation) sans donnée pour l'étayer. Si une valeur est faible, dis "ce point mérite une investigation" ou "les causes de cet écart ne peuvent pas être déterminées avec les données disponibles".
14. Pour la Data Quality, ne dis jamais "doublons". Dis systématiquement "signatures événementielles répétées possibles". Précise que "l'absence d'un event_id unique ne permet pas de confirmer qu'il s'agit de doublons."
15. observed_usage_intensity_30d correspond à : average_active_days_per_active_user_30d / 30 * 100. C'est une métrique descriptive d'intensité observée.
16. Cette métrique n'est PAS : un taux d'adoption, un DAU/MAU, un objectif métier, ou un taux d'utilisation métier cible.
17. En l'absence d'un benchmark ou d'une fréquence cible métier, ne jamais qualifier l'intensité ou la fréquence comme : faible, moyenne / modérée, élevée, bonne / mauvaise, intermittente, occasionnelle, régulière. Dire plutôt : "Cette valeur décrit l'usage observé. Son niveau ne peut pas être qualifié sans fréquence cible définie par le métier."
18. Lorsqu'une question porte spécifiquement sur "intensité d'utilisation" et que observed_usage_intensity_30d est disponible : répondre d'abord avec cette valeur, donner ensuite la fréquence moyenne comme contexte, et éventuellement la médiane. Ne pas énumérer DAU, WAU et MAU sauf si cela est utile à la question ou explicitement demandé.
19. Toujours dire "sur les 30 derniers jours disponibles" ou "sur une fenêtre de 30 jours". Ne pas dire "par mois" pour cette métrique.
20. Pour la médiane, parler de "utilisateurs actifs" et non "utilisateurs engagés".
"""


class LLMEngine:
    def __init__(self, registry: ToolRegistry, client=None, knowledge_retriever: KnowledgeRetriever | None = None):
        self.registry = registry
        self.knowledge_retriever = knowledge_retriever
        if client:
            self.client = client
        else:
            if not settings.groq_api_key:
                raise ValueError("GROQ_API_KEY n'est pas configurée.")
            self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def _get_groq_tools(self) -> list[dict[str, Any]]:
        groq_tools = []
        for tool in self.registry.list_tools():
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return groq_tools

    def chat(self, user_message: str, max_rounds: int = 3) -> AssistantResponse:
        knowledge_sources = []
        rag_context = ""
        if self.knowledge_retriever:
            try:
                results = self.knowledge_retriever.search(user_message, top_k=3)
                if results:
                    rag_context = "\n\nCONTEXTE DOCUMENTAIRE :\n"
                    for res in results:
                        rag_context += f"\n[Source: {res['source']} | Section: {res['section']}]\n{res['content']}\n"
                        knowledge_sources.append({"source": res["source"], "section": res["section"]})
            except Exception:
                rag_context = ""
        augmented_message = user_message + rag_context

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": augmented_message}
        ]

        tools = self._get_groq_tools()
        used_tools = []
        all_limitations = []

        for _ in range(max_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.1
                )
            except Exception as e:
                status_code = getattr(e, "status_code", None)

                if status_code in (400, 422):
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.0
                        )
                    except Exception as retry_e:
                        return AssistantResponse(
                            answer="Erreur lors de la communication avec l'assistant.",
                            tool_calls=used_tools,
                            limitations=all_limitations,
                            error=str(retry_e),
                            knowledge_sources=knowledge_sources
                        )
                else:
                    return AssistantResponse(
                        answer="Erreur lors de la communication avec l'assistant.",
                        tool_calls=used_tools,
                        limitations=all_limitations,
                        error=str(e),
                        knowledge_sources=knowledge_sources
                    )

            if not response.choices:
                return AssistantResponse(
                    answer="Aucune réponse du modèle.",
                    tool_calls=used_tools,
                    limitations=all_limitations,
                    error="Empty choices",
                    knowledge_sources=knowledge_sources
                )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if not tool_calls:
                return AssistantResponse(
                    answer=response_message.content or "",
                    tool_calls=used_tools,
                    limitations=all_limitations,
                    knowledge_sources=knowledge_sources
                )

            # Convert response message properly to dict to append to messages (groq requirement)
            # The python SDK allows appending the message object directly
            messages.append({
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            })

            for tc in tool_calls:
                func_name = tc.function.name
                used_tools.append(func_name)
                try:
                    kwargs = json.loads(tc.function.arguments)
                    result = self.registry.execute(func_name, **kwargs)
                except json.JSONDecodeError:
                    result = ToolResult(
                        status="invalid_request",
                        tool=func_name,
                        service="",
                        data={},
                        message="Invalid JSON arguments"
                    )
                except Exception as e:
                    result = ToolResult(
                        status="error",
                        tool=func_name,
                        service="",
                        data={},
                        message=str(e)
                    )

                if getattr(result, "limitations", None):
                    all_limitations.extend(result.limitations)

                try:
                    tool_content = json.dumps(
                        asdict(result),
                        default=str,
                        ensure_ascii=False
                    )
                except Exception:

                    tool_content = json.dumps({
                        "status": "error",
                        "message": "Impossible de sérialiser le résultat du tool"
                    })


                tool_msg = {
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": func_name,
                    "content": tool_content
                }
                messages.append(tool_msg)

        return AssistantResponse(
            answer="La limite de réflexion de l'assistant a été atteinte.",
            tool_calls=used_tools,
            limitations=all_limitations,
            error="Max tool rounds reached",
            knowledge_sources=knowledge_sources
        )

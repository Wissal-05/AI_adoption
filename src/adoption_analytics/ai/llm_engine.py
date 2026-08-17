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
                pass  # Fallback gracefully to no RAG if retriever fails

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
            messages.append(response_message)

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

                tool_msg = {
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": func_name,
                    "content": json.dumps(asdict(result))
                }
                messages.append(tool_msg)

        return AssistantResponse(
            answer="La limite de réflexion de l'assistant a été atteinte.",
            tool_calls=used_tools,
            limitations=all_limitations,
            error="Max tool rounds reached",
            knowledge_sources=knowledge_sources
        )

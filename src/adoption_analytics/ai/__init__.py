"""Module IA — fabrique de moteurs d'assistant."""

from adoption_analytics.ai.port import AssistantPort
from adoption_analytics.ai.keyword_engine import KeywordEngine
from config.settings import settings


def get_assistant() -> AssistantPort:
    """Conserve pour la rétrocompatibilité stricte si nécessaire ailleurs,
    bien que app.py utilisera plutôt create_assistant_engine."""
    return KeywordEngine()

def create_assistant_engine(dashboard_service=None):
    """Factory pour l'Assistant IA (Groq LLM ou fallback Keyword).

    Retourne une instance de LLMEngine si GROQ_API_KEY est présente
    et que le settings.assistant_engine == 'llm' (ou si la clé est juste là pour ce MVP).
    Sinon, retourne KeywordEngine.
    """
    if settings.assistant_engine.lower() == "llm" and settings.groq_api_key:
        try:
            from adoption_analytics.ai.llm_engine import LLMEngine
            from adoption_analytics.ai.tool_registry import ToolRegistry
            from adoption_analytics.ai.knowledge_retriever import KnowledgeRetriever

            # On instancie le registry avec le service fourni par l'app Streamlit
            registry = ToolRegistry(dashboard_service)

            # Initialisation du retriever RAG
            retriever = None
            try:
                retriever = KnowledgeRetriever()
                retriever.build_index()
            except Exception:
                pass # Si le RAG échoue, on continue sans

            return LLMEngine(registry=registry, knowledge_retriever=retriever)
        except Exception as e:
            # En cas d'erreur d'import ou de clé, on retourne le fallback silencieusement
            # (ou on pourrait logger l'erreur). L'UI signalera le mode déterministe.
            pass

    # Fallback par défaut (soit configuré sur keyword, soit pas de clé, soit erreur)
    return KeywordEngine()


# Fonction de compatibilité ascendante avec l'ancien assistant.py
def answer_question(question: str, usage_df, web_logs_df) -> str:
    """Alias de compatibilité pour l'ancien assistant.answer_question()."""
    import pandas as pd
    assistant = KeywordEngine()
    return assistant.answer(
        question,
        context={
            "usage_df": usage_df if isinstance(usage_df, pd.DataFrame) else pd.DataFrame(),
            "web_logs_df": web_logs_df if isinstance(web_logs_df, pd.DataFrame) else pd.DataFrame(),
        },
    )

__all__ = ["AssistantPort", "KeywordEngine", "get_assistant", "answer_question", "create_assistant_engine"]

"""Module IA — fabrique de moteurs d'assistant.

Utilise la variable de configuration `settings.assistant_engine` pour
instancier le moteur approprié :
  - "keyword"  → KeywordEngine (défaut, sans dépendance externe)
  - "llm"      → LLMEngine (nécessite LangChain + clé API)

Usage dans app.py :
    from adoption_analytics.ai import get_assistant
    assistant = get_assistant()
    response = assistant.answer(question, context={"usage_df": df, "web_logs_df": logs_df})
"""

from adoption_analytics.ai.port import AssistantPort
from adoption_analytics.ai.keyword_engine import KeywordEngine


def get_assistant() -> AssistantPort:
    """Instancie et retourne le moteur d'assistant configuré.

    Le moteur est sélectionné via `settings.assistant_engine` (variable d'env
    ASSISTANT_ENGINE). Valeurs supportées : "keyword" (défaut), "llm".

    Returns:
        Instance de AssistantPort prête à l'emploi.

    Raises:
        ValueError: si le moteur configuré n'est pas reconnu.
    """
    from config.settings import settings

    engine = settings.assistant_engine.lower()

    if engine == "keyword":
        return KeywordEngine()

    if engine == "llm":
        try:
            from adoption_analytics.ai.llm_engine import LLMEngine  # type: ignore[import]
            return LLMEngine()
        except ImportError as exc:
            raise ImportError(
                "Le moteur 'llm' nécessite des dépendances supplémentaires. "
                "Vérifiez que langchain et langchain-openai sont installés, "
                "et que OPENAI_API_KEY est défini dans votre .env."
            ) from exc

    raise ValueError(
        f"Moteur d'assistant inconnu : '{engine}'. "
        f"Valeurs supportées : 'keyword', 'llm'."
    )


# Fonction de compatibilité ascendante avec l'ancien assistant.py
def answer_question(question: str, usage_df, web_logs_df) -> str:
    """Alias de compatibilité pour l'ancien assistant.answer_question().

    Préférer get_assistant().answer(question, context={...}) dans le nouveau code.
    """
    import pandas as pd
    assistant = get_assistant()
    return assistant.answer(
        question,
        context={
            "usage_df": usage_df if isinstance(usage_df, pd.DataFrame) else pd.DataFrame(),
            "web_logs_df": web_logs_df if isinstance(web_logs_df, pd.DataFrame) else pd.DataFrame(),
        },
    )


__all__ = ["AssistantPort", "KeywordEngine", "get_assistant", "answer_question"]

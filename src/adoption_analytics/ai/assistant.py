import pandas as pd

from adoption_analytics.metrics.adoption import (
    departmental_breakdown,
    find_underused_services,
    inactive_users,
)
from adoption_analytics.metrics.security import detect_suspicious_routes


def answer_question(question: str, usage_df: pd.DataFrame, web_logs_df: pd.DataFrame) -> str:
    normalized = question.lower()

    if any(term in normalized for term in ["moins utilisé", "least-used", "sous-utilisé", "underused"]):
        underused = find_underused_services(usage_df).head(5)
        return _format_records("Services les moins utilisés", underused)

    if any(term in normalized for term in ["département", "department"]):
        breakdown = departmental_breakdown(usage_df).head(10)
        return _format_records("Usage par département", breakdown)

    if any(term in normalized for term in ["inactif", "inactive"]):
        users = inactive_users(usage_df).head(10)
        return _format_records("Utilisateurs inactifs", users)

    if any(term in normalized for term in ["attaque", "malicious", "suspicious", "sécurité", "security"]):
        suspicious = detect_suspicious_routes(web_logs_df).head(10)
        return _format_records("Routes suspectes détectées", suspicious)

    return (
        "Je peux répondre aux questions sur les services les moins utilisés, l'usage par département, "
        "les utilisateurs inactifs, les baisses d'adoption et les routes suspectes. "
        "Pour une réponse générative plus avancée, branchez ici LangChain avec un LLM et fournissez-lui "
        "les tableaux agrégés comme contexte contrôlé."
    )


def _format_records(title: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"{title}: aucune donnée correspondante."

    lines = [f"{title}:"]
    for record in df.to_dict(orient="records"):
        compact = ", ".join(f"{key}={value}" for key, value in record.items())
        lines.append(f"- {compact}")
    return "\n".join(lines)

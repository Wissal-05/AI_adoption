"""Moteur d'assistant par correspondance de mots-clés.

Ce moteur répond aux questions en identifiant des mots-clés dans la question
et en retournant les métriques pré-calculées correspondantes. Il ne nécessite
aucune API externe et fonctionne hors-ligne.

Il implémente AssistantPort et peut être remplacé par tout autre moteur
(LangChain, Gemini, OpenAI) sans modifier l'UI.
"""

import pandas as pd

from adoption_analytics.ai.port import AssistantPort

from adoption_analytics.metrics.adoption import (
    compute_usage_frequency,
    departmental_breakdown,
    find_underused_services,
    inactive_users,
)
from adoption_analytics.metrics.learning_center import prepare_daily_trend
from adoption_analytics.metrics.security import detect_suspicious_routes
from adoption_analytics.services.adoption_metrics_service import (
    AdoptionMetricsService,
)

class KeywordEngine(AssistantPort):
    """Moteur d'assistant basé sur la correspondance de mots-clés.

    Analyse la question en langage naturel, détecte l'intention à partir
    de mots-clés, et retourne les métriques calculées correspondantes.

    Ce moteur est déterministe, rapide et ne nécessite aucune dépendance externe.
    Pour des réponses génératives plus avancées, utiliser LLMEngine.
    """

    # Mapping intention → mots-clés de détection
    _INTENT_KEYWORDS: dict[str, list[str]] = {
        "mau": [
                    "mau",
                    "monthly active users",
                    "utilisateurs actifs mensuels",
                    "utilisateur actif mensuel",
                ],
        "dau": [
            "dau",
            "daily active users",
            "utilisateurs actifs quotidiens",
            "utilisateur actif quotidien",
        ],
        "wau": [
            "wau",
            "weekly active users",
            "utilisateurs actifs hebdomadaires",
            "utilisateur actif hebdomadaire",
        ],
        "adoption_summary": [
            "kpi d'adoption",
            "kpis d'adoption",
            "résumé adoption",
            "indicateurs d'adoption",
            "dau wau mau",
        ],
        "evolution": [
            "évolution",
            "evolution",
            "tendance",
            "trend",
            "30 jours",
            "dernier mois",
        ],
                "frequency": [
            "fréquence",
            "frequence",
            "frequency",
            "intensité",
            "intensite",
            "événements par utilisateur",
            "evenements par utilisateur",
            "events per user",
            "jours actifs",
        ],
        "usage_rate": [
            "taux d'utilisation",
            "taux utilisation",
            "usage rate",
            "adoption rate",
            "taux d'adoption",
            "taux adoption",
        ],
        "underused": ["moins utilisé", "least-used", "sous-utilisé", "underused", "peu utilisé"],
        "department": ["département", "department", "service métier", "équipe"],
        "inactive": ["inactif", "inactive", "absent", "dormant", "plus actif"],
        "security": ["attaque", "malicious", "suspicious", "sécurité", "security", "route suspecte", "intrusion", "suspecte"],
        
    }
    

    def answer(self, question: str, context: dict) -> str:
        """Répond à une question par correspondance de mots-clés.

        Args:
            question: Question en langage naturel.
            context: Doit contenir "usage_df" et "web_logs_df".

        Returns:
            Réponse formatée en texte.
        """
        normalized = question.lower().replace("’", "'")
        usage_df: pd.DataFrame = context.get("usage_df", pd.DataFrame())
        web_logs_df: pd.DataFrame = context.get("web_logs_df", pd.DataFrame())
        daily_kpis_df: pd.DataFrame = context.get("daily_kpis", pd.DataFrame())

        intent = self._detect_intent(normalized)

        handlers = {
            "mau": self._handle_mau,
            "dau": self._handle_dau,
            "wau": self._handle_wau,
            "adoption_summary": self._handle_adoption_summary,
            "frequency": self._handle_frequency,
            "usage_rate": self._handle_usage_rate,
            "evolution": self._handle_evolution,
            "underused": self._handle_underused,
            "department": self._handle_department,
            "inactive": self._handle_inactive,
            "security": self._handle_security,
        }

        handler = handlers.get(intent)

        if handler is not None:
            return handler(usage_df, web_logs_df, daily_kpis_df)
       
        return self._default_response()

    def _handle_mau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        metrics = self._adoption_metrics(usage_df)
        return f"**MAU :** {metrics['mau']:,} utilisateurs actifs."


    def _handle_dau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        metrics = self._adoption_metrics(usage_df)
        return f"**DAU :** {metrics['dau']:,} utilisateurs actifs."

    def _handle_wau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        metrics = self._adoption_metrics(usage_df)
        return f"**WAU :** {metrics['wau']:,} utilisateurs actifs."

    def _handle_evolution(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        trend = prepare_daily_trend(daily_kpis_df)

        if trend.empty:
            return "Aucune donnée d’évolution n’est disponible."

        recent = trend.tail(30)
        first = recent.iloc[0]
        last = recent.iloc[-1]

        return (
            f"**Évolution sur {len(recent)} jours :**\n\n"
            f"- DAU : {first['dau']:,} → {last['dau']:,}\n"
            f"- WAU : {first['wau']:,} → {last['wau']:,}\n"
            f"- MAU : {first['mau']:,} → {last['mau']:,}"
        )

    def _handle_adoption_summary(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        metrics = self._adoption_metrics(usage_df)

        return (
            "**KPI d’adoption :**\n"
            f"- DAU : {metrics['dau']:,}\n"
            f"- WAU : {metrics['wau']:,}\n"
            f"- MAU : {metrics['mau']:,}"
        )

    def _handle_frequency(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        frequency = compute_usage_frequency(usage_df)

        return (
            "**Fréquence d’utilisation :**\n"
            f"- Utilisateurs actifs : {frequency['active_users']:,}\n"
            f"- Événements totaux : {frequency['total_events']:,}\n"
            f"- Événements moyens par utilisateur actif : "
            f"{frequency['avg_events_per_active_user']:.2f}\n"
            f"- Jours actifs moyens par utilisateur : "
            f"{frequency['avg_active_days_per_user']:.2f}"
        )

    def _handle_usage_rate(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        return (
            "**Taux d’utilisation : non calculable actuellement.**\n\n"
            "Le moteur KPI sait calculer ce taux, mais le référentiel des "
            "utilisateurs éligibles au service n’est pas disponible dans les "
            "données chargées.\n\n"
            "Formule prévue :\n"
            "`taux d’utilisation = utilisateurs actifs / utilisateurs éligibles × 100`\n\n"
            "Données nécessaires : référentiel RH, Active Directory, Azure AD, "
            "IAM ou matrice d’accès indiquant quels utilisateurs ont accès au service."
        )

    def _handle_underused(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        result = find_underused_services(usage_df).head(5)
        return self._format_records("Services les moins utilisés", result)

    def _handle_department(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        result = departmental_breakdown(usage_df).head(10)
        return self._format_records("Usage par département", result)

    def _handle_inactive(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        result = inactive_users(usage_df).head(10)
        return self._format_records("Utilisateurs inactifs", result)

    def _handle_security(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        result = detect_suspicious_routes(web_logs_df).head(10)
        return self._format_records("Routes suspectes détectées", result)

    def _detect_intent(self, normalized_question: str) -> str | None:
        """Détecte l'intention à partir des mots-clés de la question."""
        for intent, keywords in self._INTENT_KEYWORDS.items():
            if any(kw in normalized_question for kw in keywords):
                return intent
        return None

    @staticmethod
    def _adoption_metrics(usage_df: pd.DataFrame) -> dict:
        """Calcule les KPI d'adoption."""
        return AdoptionMetricsService.compute(usage_df)

    @staticmethod
    def _format_records(title: str, df: pd.DataFrame) -> str:
        if df.empty:
            return f"{title}: aucune donnée correspondante."
        lines = [f"**{title}:**"]
        for record in df.to_dict(orient="records"):
            compact = ", ".join(f"{key}={value}" for key, value in record.items())
            lines.append(f"- {compact}")
        return "\n".join(lines)

    @staticmethod
    def _default_response() -> str:
                return (
            "Je peux répondre aux questions sur :\n"
            "- Les **KPI d’adoption** : DAU, WAU et MAU\n"
            "- L’**évolution temporelle** des KPI\n"
            "- La **fréquence d’utilisation**\n"
            "- Le **taux d’utilisation** et les données nécessaires pour le calculer\n"
            "- Les **services les moins utilisés**\n"
            "- L’**usage par département**\n"
            "- Les **utilisateurs inactifs**\n"
            "- Les **routes suspectes** (sécurité)\n\n"
            "Exemples :\n"
            "- Quel est le DAU ?\n"
            "- Donne-moi les KPI d’adoption\n"
            "- Quelle est la fréquence d’utilisation ?\n"
            "- Quel est le taux d’utilisation ?\n"
            "- Quels sont les services sous-utilisés ?\n\n"
            "Pour des réponses génératives plus avancées, activez le moteur LLM "
            "en définissant `ASSISTANT_ENGINE=llm` dans votre fichier `.env`."
        )
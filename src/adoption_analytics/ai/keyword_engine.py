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
        "department": [
            "département",
            "departement",
            "department",
            "direction",
            "entité",
            "entite",
            "entity",
            "service métier",
            "service metier",
            "équipe",
            "equipe",
        ],
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

        comparison_intent = self._is_comparison_question(normalized)

        if comparison_intent:
            return self._handle_service_comparison(
                usage_df,
                daily_kpis_df,
                normalized,
            )

        detected_service = self._detect_service(
            normalized,
            usage_df,
            daily_kpis_df,
        )

        if detected_service is not None:
            usage_df = self._filter_by_service(usage_df, detected_service)

            if "service" in daily_kpis_df.columns:
                daily_kpis_df = self._filter_by_service(
                    daily_kpis_df,
                    detected_service,
                )
            else:
                daily_kpis_df = pd.DataFrame()

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
            response = handler(usage_df, web_logs_df, daily_kpis_df)
            return self._add_service_context_to_response(
                response,
                detected_service,
                intent,
            )
       
        return self._default_response()

    def _handle_mau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        latest = self._latest_daily_kpis(daily_kpis_df)

        if latest is not None:
            return f"**MAU :** {latest['mau']:,} utilisateurs actifs."

        metrics = self._adoption_metrics(usage_df)
        return f"**MAU :** {metrics['mau']:,} utilisateurs actifs."

    def _handle_dau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        latest = self._latest_daily_kpis(daily_kpis_df)

        if latest is not None:
            return f"**DAU :** {latest['dau']:,} utilisateurs actifs."

        metrics = self._adoption_metrics(usage_df)
        return f"**DAU :** {metrics['dau']:,} utilisateurs actifs."

    def _handle_wau(
        self,
        usage_df: pd.DataFrame,
        web_logs_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str:
        latest = self._latest_daily_kpis(daily_kpis_df)

        if latest is not None:
            return f"**WAU :** {latest['wau']:,} utilisateurs actifs."

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
        latest = self._latest_daily_kpis(daily_kpis_df)

        if latest is not None:
            return (
                "**KPI d’adoption :**\n"
                f"- DAU : {latest['dau']:,}\n"
                f"- WAU : {latest['wau']:,}\n"
                f"- MAU : {latest['mau']:,}"
            )

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
    def _detect_service(
        normalized_question: str,
        usage_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> str | None:
        """Détecte le service mentionné dans la question."""

        known_services = []

        for dataframe in [usage_df, daily_kpis_df]:
            if not dataframe.empty and "service" in dataframe.columns:
                known_services.extend(
                    dataframe["service"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

        service_aliases = {
            "booking": ["booking", "réservation", "reservation"],
            "learning center": [
                "learning center",
                "learning-center",
                "learning_center",
                "lc",
            ],
        }

        for canonical_service, aliases in service_aliases.items():
            if any(alias in normalized_question for alias in aliases):
                for service in known_services:
                    if service.lower() == canonical_service:
                        return service

                return canonical_service.title()

        for service in known_services:
            if service.lower() in normalized_question:
                return service

        return None

    @staticmethod
    def _filter_by_service(
        dataframe: pd.DataFrame,
        service: str | None,
    ) -> pd.DataFrame:
        """Filtre un dataframe par service si la colonne service existe."""

        if service is None or dataframe.empty or "service" not in dataframe.columns:
            return dataframe

        filtered = dataframe[
            dataframe["service"].astype(str).str.lower() == service.lower()
        ]

        return filtered

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
    def _latest_daily_kpis(daily_kpis_df: pd.DataFrame) -> dict | None:
        if daily_kpis_df.empty:
            return None

        data = daily_kpis_df.copy()

        metric_columns = {
            "dau": "dau" if "dau" in data.columns else "dau_approx",
            "wau": "wau" if "wau" in data.columns else "wau_approx",
            "mau": "mau" if "mau" in data.columns else "mau_approx",
        }

        required_columns = {"date", *metric_columns.values()}

        if not required_columns.issubset(data.columns):
            return None

        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data = data.dropna(subset=["date"]).sort_values("date")

        if data.empty:
            return None

        last = data.iloc[-1]

        return {
            "dau": int(last[metric_columns["dau"]]),
            "wau": int(last[metric_columns["wau"]]),
            "mau": int(last[metric_columns["mau"]]),
            "date": last["date"].date(),
        }

    @staticmethod
    def _add_service_context_to_response(
        response: str,
        detected_service: str | None,
        intent: str | None,
    ) -> str:
        """Ajoute le nom du service dans la réponse lorsque la question cible un service."""

        if detected_service is None or intent is None:
            return response

        service_label = detected_service

        replacements = {
            "mau": {
                "**MAU :**": f"**MAU de {service_label} :**",
            },
            "dau": {
                "**DAU :**": f"**DAU de {service_label} :**",
            },
            "wau": {
                "**WAU :**": f"**WAU de {service_label} :**",
            },
            "frequency": {
                "**Fréquence d’utilisation :**": (
                    f"**Fréquence d’utilisation de {service_label} :**"
                ),
                "**FrÃ©quence dâ€™utilisation :**": (
                    f"**Fréquence d’utilisation de {service_label} :**"
                ),
            },
            "adoption_summary": {
                "**KPI d’adoption :**": f"**KPI d’adoption de {service_label} :**",
                "**KPI dâ€™adoption :**": f"**KPI d’adoption de {service_label} :**",
            },
        }

        for source, target in replacements.get(intent, {}).items():
            if source in response:
                return response.replace(source, target, 1)

        return response

    @staticmethod
    def _is_comparison_question(normalized_question: str) -> bool:
        """Détecte si la question demande une comparaison entre services."""

        comparison_keywords = [
            "compare",
            "comparaison",
            "comparer",
            "versus",
            " vs ",
            "entre",
            "le plus",
            "la plus",
            "plus de",
            "plus grand",
            "plus grande",
            "meilleur",
            "meilleure",
        ]

        return any(keyword in normalized_question for keyword in comparison_keywords)
    
    @staticmethod
    def _detect_comparison_metric(normalized_question: str) -> str | None:
        """Détecte le KPI à comparer dans une question."""

        if "dau" in normalized_question or "quotidien" in normalized_question:
            return "dau"

        if "wau" in normalized_question or "hebdomadaire" in normalized_question:
            return "wau"

        if "mau" in normalized_question or "mensuel" in normalized_question:
            return "mau"

        if (
            "fréquence" in normalized_question
            or "frequence" in normalized_question
            or "frequency" in normalized_question
            or "événements par utilisateur" in normalized_question
            or "evenements par utilisateur" in normalized_question
        ):
            return "frequency"

        return None

    @staticmethod
    def _compute_metrics_by_service(
        usage_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
    ) -> dict[str, dict]:
        """Calcule les KPI par service pour les comparaisons."""

        results: dict[str, dict] = {}

        if usage_df.empty or "service" not in usage_df.columns:
            return results

        services = sorted(
            usage_df["service"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        for service in services:
            service_usage = usage_df[
                usage_df["service"].astype(str).str.lower() == service.lower()
            ]

            service_daily_kpis = pd.DataFrame()

            if not daily_kpis_df.empty and "service" in daily_kpis_df.columns:
                service_daily_kpis = daily_kpis_df[
                    daily_kpis_df["service"].astype(str).str.lower() == service.lower()
                ]

            latest = KeywordEngine._latest_daily_kpis(service_daily_kpis)

            if latest is not None:
                metrics = {
                    "dau": latest["dau"],
                    "wau": latest["wau"],
                    "mau": latest["mau"],
                }
            else:
                metrics = KeywordEngine._adoption_metrics(service_usage)

            frequency = compute_usage_frequency(service_usage)

            metrics["frequency"] = frequency["avg_events_per_active_user"]
            metrics["active_users"] = frequency["active_users"]
            metrics["total_events"] = frequency["total_events"]

            results[service] = metrics

        return results

    @staticmethod
    def _format_metric_value(metric: str, value: float | int) -> str:
        """Formate une valeur de KPI."""

        if metric == "frequency":
            return f"{float(value):.2f}"

        return f"{int(round(value)):,}"

    def _handle_service_comparison(
        self,
        usage_df: pd.DataFrame,
        daily_kpis_df: pd.DataFrame,
        normalized_question: str,
    ) -> str:
        """Répond aux questions de comparaison entre services."""

        metrics_by_service = self._compute_metrics_by_service(
            usage_df,
            daily_kpis_df,
        )

        if not metrics_by_service:
            return (
                "Aucune donnée suffisante n’est disponible pour comparer les services."
            )

        selected_metric = self._detect_comparison_metric(normalized_question)

        metric_labels = {
            "dau": "DAU",
            "wau": "WAU",
            "mau": "MAU",
            "frequency": "fréquence moyenne",
        }

        if selected_metric is not None:
            label = metric_labels[selected_metric]

            rows = []
            for service, metrics in metrics_by_service.items():
                value = metrics.get(selected_metric, 0)
                rows.append((service, value))

            rows = sorted(rows, key=lambda item: item[1], reverse=True)

            leader_service, leader_value = rows[0]

            lines = [
                f"**Comparaison {label} par service :**",
            ]

            for service, value in rows:
                lines.append(
                    f"- {service} : {self._format_metric_value(selected_metric, value)}"
                )

            lines.append("")
            lines.append(
                f"**Service le plus élevé :** {leader_service} "
                f"avec {self._format_metric_value(selected_metric, leader_value)}."
            )

            if selected_metric == "frequency":
                lines.append(
                    "La fréquence moyenne mesure l’intensité d’usage par utilisateur actif. "
                    "Une valeur élevée peut indiquer un usage fort ou une activité concentrée "
                    "sur certains profils."
                )
            else:
                lines.append(
                    "Cette comparaison mesure l’usage observé. Pour conclure sur l’adoption réelle, "
                    "il faut comparer ces résultats à la population éligible de chaque service."
                )

            return "\n".join(lines)

        lines = [
            "**Comparaison globale par service :**",
        ]

        for service, metrics in metrics_by_service.items():
            lines.append(
                f"- {service} : "
                f"DAU={self._format_metric_value('dau', metrics.get('dau', 0))}, "
                f"WAU={self._format_metric_value('wau', metrics.get('wau', 0))}, "
                f"MAU={self._format_metric_value('mau', metrics.get('mau', 0))}, "
                f"fréquence={self._format_metric_value('frequency', metrics.get('frequency', 0))}"
            )

        lines.append("")
        lines.append(
            "Cette comparaison donne une lecture multi-services de l’usage observé. "
            "Le taux d’utilisation réel reste non calculable sans population éligible par service."
        )

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
"""Interface abstraite du moteur d'assistance IA.

AssistantPort définit le contrat que tout moteur d'assistant doit respecter.
L'UI appelle uniquement cette interface, ce qui permet de substituer le moteur
(keyword → LangChain → LLM cloud) sans modifier app.py.

## Ajouter un nouveau moteur

1. Créer `ai/mon_moteur.py` avec une classe héritant de AssistantPort.
2. Implémenter la méthode `answer()`.
3. Déclarer le moteur dans `settings.assistant_engine` (ex: "mon_moteur").
4. Enregistrer le moteur dans `ai/__init__.py` via la factory `get_assistant()`.
"""

from abc import ABC, abstractmethod


class AssistantPort(ABC):
    """Interface abstraite pour les moteurs d'assistant IA."""

    @abstractmethod
    def answer(self, question: str, context: dict) -> str:
        """Répond à une question en langage naturel à partir du contexte fourni.

        Args:
            question: Question posée par l'utilisateur en langage naturel.
            context: Dictionnaire de données contextuelles. Les clés standard sont :
                - "usage_df": pd.DataFrame des événements d'usage filtrés.
                - "web_logs_df": pd.DataFrame des logs web.
                - "adoption_metrics": dict[str, float] des métriques calculées.
                Les moteurs peuvent ignorer les clés qu'ils ne supportent pas.

        Returns:
            Réponse formatée en texte (markdown accepté).
        """

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

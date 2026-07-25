# Adoption Assistant

Assistant IA pour l'analyse de l'adoption et de l'utilisation des services numériques en entreprise.

Le projet vise à aider les responsables IT à exploiter les données d'usage issues de différentes applications afin de suivre l'adoption des services, détecter les usages faibles et interroger les indicateurs en langage naturel.

---

## Objectif du projet

Les organisations utilisent plusieurs services numériques :

- Microsoft 365 ;
- Learning Center ;
- applications web internes ;
- VPN ;
- applications métiers ;
- outils collaboratifs.

Même si des données d'usage existent dans les logs, APIs, annuaires ou outils de supervision, leur exploitation reste complexe.

L'objectif de ce projet est de développer une solution capable de :

- préparer et nettoyer les données d'utilisation ;
- calculer automatiquement des indicateurs d'adoption ;
- visualiser les indicateurs dans un tableau de bord interactif ;
- répondre aux questions des responsables IT en langage naturel.

---

## Fonctionnalités actuelles

Le projet implémente actuellement :

- ingestion et normalisation des données Learning Center ;
- parsing des logs Nginx ;
- persistance intermédiaire des données préparées ;
- calcul des KPI d'adoption ;
- tableau de bord Streamlit ;
- assistant conversationnel par mots-clés ;
- détection de routes suspectes ;
- suite de tests automatisés.

---

## Indicateurs d'adoption implémentés

Le moteur analytique principal se trouve dans :

```text
src/adoption_analytics/metrics/adoption.py

## Exemples de questions :

Quel est le DAU ?
Quel est le WAU ?
Quel est le MAU ?
Donne-moi les KPI d'adoption.
Donne-moi l'évolution sur 30 jours.
Quelle est la fréquence d'utilisation ?
Quel est le taux d'utilisation ?
Quels sont les services sous-utilisés ?
Quelle direction utilise le plus le service ?
Quels sont les utilisateurs inactifs ?
Y a-t-il des routes suspectes ?

## Technologies utilisées

Python ;
Pandas ;
Streamlit ;
Plotly ;
Pytest ;
PowerShell ;
Groq / LLM optionnel ;
Microsoft Graph API prévu pour les futures sources.
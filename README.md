# AI Adoption Assistant

## 1. Présentation du projet

AI Adoption Assistant est un projet d’analyse de l’adoption et de l’utilisation des services numériques en entreprise.

L’objectif est de construire une solution capable de :

- analyser les données d’usage de plusieurs applications ;
- calculer automatiquement des indicateurs d’adoption ;
- centraliser les résultats dans un dashboard interactif ;
- interpréter les KPI à travers des explications contextuelles ;
- préparer l’intégration future d’un assistant IA conversationnel et d’un moteur LLM.

Le projet est actuellement développé sous forme de POC avec deux services intégrés :

- **Learning Center**
- **Booking**

---

## 2. Objectifs fonctionnels

Le projet vise à répondre à des questions comme :

- Quel est le nombre d’utilisateurs actifs d’un service ?
- Comment évolue l’usage dans le temps ?
- Quel service est le plus utilisé ?
- Quel campus ou quelle entité utilise le plus une application ?
- Quelles sont les pages, routes, API ou actions métier les plus utilisées ?
- Quelles données manquent pour calculer un vrai taux d’adoption ?
- Comment interpréter les KPI affichés dans le dashboard ?

---

## 3. Indicateurs calculés

Les principaux KPI suivis sont :

| KPI | Description |
|---|---|
| DAU | Daily Active Users — utilisateurs actifs uniques sur une journée |
| WAU | Weekly Active Users — utilisateurs actifs uniques sur 7 jours |
| MAU | Monthly Active Users — utilisateurs actifs uniques sur 30 jours ou sur le mois |
| Fréquence moyenne | Nombre moyen d’événements par utilisateur actif |
| Événements | Volume total d’actions ou événements observés |
| Part d’usage | Répartition de l’usage par service, entité, campus ou interaction |
| Taux d’utilisation | Utilisateurs actifs / population éligible |

Important :

```text
DAU, WAU et MAU mesurent des utilisateurs uniques actifs, pas le nombre total d’événements.
```

Le taux d’utilisation réel nécessite une donnée supplémentaire :

```text
Taux d’utilisation = utilisateurs actifs / population éligible × 100
```

Cette population éligible n’est pas encore disponible pour tous les services, donc certains taux sont affichés comme :

```text
Non calculable
```

---

## 4. Sources de données actuelles

### Learning Center

Le service Learning Center est analysé à partir de logs web.

Données exploitées :

- événements web ;
- routes ;
- pages ;
- appels API ;
- utilisateurs observés ;
- statuts HTTP ;
- sessions lorsque disponibles.

Limite principale :

```text
Le mapping utilisateur vers entité, campus ou direction est manquant.
```

---

### Booking

Le service Booking est analysé à partir d’événements applicatifs.

Données exploitées :

- événements métier ;
- actions applicatives ;
- utilisateurs observés ;
- campus ;
- évolution temporelle.

Exemples d’actions observées :

- `UPDATE_GUEST`
- `UPDATE_GUEST_REQUEST`
- `CREATE_HOUSING`
- `ASSIGN_ROOM`

Limite principale :

```text
La population éligible par service/campus est manquante.
```

---

## 5. Architecture logique

Le projet suit une architecture orientée données :

```text
Sources brutes
    ↓
Extraction
    ↓
Nettoyage / normalisation
    ↓
Modèle de données commun
    ↓
Calcul des KPI
    ↓
Dashboard Streamlit
    ↓
Interprétation des résultats
    ↓
Assistant IA / recommandations
```

L’idée principale est de ne pas construire un dashboard séparé pour chaque application.

Chaque service est transformé vers un modèle commun contenant notamment :

- `event_timestamp`
- `user_id`
- `service`
- `action`
- `department`
- `source`

Ce modèle permet d’appliquer les mêmes calculs KPI à plusieurs applications.

---

## 6. Structure du projet

Structure simplifiée :

```text
AI_adoption/
│
├── app.py
├── docs/
│   ├── common_data_model.md
│   └── data_requests.md
│
├── src/
│   └── adoption_analytics/
│       ├── ai/
│       ├── data_sources/
│       ├── metrics/
│       ├── services/
│       └── storage/
│
├── tests/
│   ├── test_adoption_metrics.py
│   ├── test_assistant.py
│   ├── test_booking_source.py
│   ├── test_connectors.py
│   ├── test_ingestion.py
│   ├── test_learning_center_metrics.py
│   ├── test_security_metrics.py
│   └── test_services.py
│
├── pyproject.toml
└── README.md
```

---

## 7. Dashboard actuel

Le dashboard contient plusieurs onglets, dont le plus important est :

```text
Dashboard adoption
```

Cet onglet centralise l’analyse multi-services.

### Sections principales

| Section | Rôle |
|---|---|
| Vue d’ensemble KPI | Affiche DAU, WAU, MAU et fréquence moyenne |
| Évolution de l’adoption | Montre l’évolution des KPI dans le temps |
| Usage par entité / campus | Compare l’usage par organisation lorsque disponible |
| Top interactions | Affiche les pages, routes, API ou actions métier les plus fréquentes |
| Données manquantes / Qualité des données | Montre les limites actuelles des données |

Chaque bloc possède un popover :

```text
💡 Interprétation IA
```

Ce popover fournit :

- une observation ;
- une interprétation ;
- une recommandation.

Les interprétations actuelles sont générées par règles contrôlées à partir des KPI calculés et des données disponibles.

Le LLM sera ajouté plus tard pour enrichir la formulation, mais il ne calculera pas les KPI.

---

## 8. Qualité des données

Le dashboard distingue clairement les données disponibles et les données manquantes.

Exemples d’affichage :

| Cas | Affichage |
|---|---|
| Entité ou campus absent | `Non renseigné` |
| Population éligible absente | `Manquante` |
| Taux d’utilisation impossible | `Non calculable` |
| Données incomplètes | `Partiel` ou `À compléter` |

Cette approche évite d’inventer des valeurs et permet de garder une analyse fiable.

---

## 9. Installation

### 9.1 Cloner le projet

```bash
git clone https://github.com/Wissal-05/AI_adoption.git
cd AI_adoption
```

### 9.2 Créer un environnement virtuel

Sous Windows PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 9.3 Installer les dépendances

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

Selon la configuration locale, il peut aussi être nécessaire d’installer les dépendances de développement :

```powershell
python -m pip install pytest streamlit pandas altair
```

---

## 10. Lancer l’application

Commande principale :

```powershell
python -m streamlit run app.py
```

L’application sera disponible localement, par exemple :

```text
http://localhost:8501
```

---

## 11. Lancer les tests

Commande :

```powershell
python -m pytest
```

État actuel attendu :

```text
61 passed
```

Deux warnings peuvent apparaître actuellement :

- warning Pandas lié au parsing de dates ;
- warning Pytest cache lié à OneDrive / permissions Windows.

Ces warnings ne bloquent pas l’exécution du projet.

---

## 12. Documentation disponible

Le dossier `docs/` contient :

| Document | Description |
|---|---|
| `common_data_model.md` | Décrit le modèle de données commun utilisé pour harmoniser les sources |
| `data_requests.md` | Liste les données nécessaires à demander pour améliorer l’analyse d’adoption |

Ces documents servent à :

- expliquer l’architecture ;
- préparer les réunions ;
- cadrer les besoins en données ;
- alimenter le rapport final ;
- justifier les limites actuelles.

---

## 13. Données nécessaires pour améliorer l’analyse

Les données actuelles permettent de mesurer l’usage observé.

Pour mesurer une adoption métier complète, il faut encore collecter :

1. population éligible par service ;
2. mapping utilisateur vers entité, campus ou direction ;
3. dictionnaire des actions métier ;
4. seuils métier d’adoption ;
5. calendrier métier ou incidents techniques ;
6. liste officielle des services prioritaires.

Ces éléments permettront de calculer :

- taux d’utilisation réel ;
- adoption par direction ;
- adoption par campus ;
- services sous-utilisés ;
- alertes fiables ;
- recommandations plus précises.

---

## 14. Assistant IA

Le projet contient une première base d’assistant.

Objectif futur :

- répondre aux questions sur les KPI ;
- détecter le service mentionné dans la question ;
- détecter le KPI demandé ;
- comparer plusieurs services ;
- expliquer les données manquantes ;
- générer des recommandations.

Exemples de questions cibles :

```text
Quel est le MAU de Booking ?
Quel est le DAU du Learning Center ?
Compare Booking et Learning Center.
Quel campus utilise le plus Booking ?
Pourquoi le taux d’utilisation est non calculable ?
Quelles données manquent pour mesurer l’adoption réelle ?
```

---

## 15. Intégration LLM prévue

L’intégration LLM n’est pas encore activée dans le dashboard principal.

Approche prévue :

```text
KPI calculés par Python
    ↓
Contexte structuré
    ↓
Moteur d’interprétation contrôlé
    ↓
LLM optionnel pour reformulation
    ↓
Popover / Assistant IA
```

Principe important :

```text
Le LLM ne calcule pas les indicateurs.
Il interprète uniquement des résultats déjà calculés.
```

Cela permet de limiter :

- les hallucinations ;
- les erreurs de calcul ;
- les problèmes de confidentialité ;
- la dépendance à une API externe.

---

## 16. Matomo

Matomo est envisagé comme source future de données web analytics.

Positionnement :

```text
Matomo = source de collecte web analytics
Dashboard = couche d’analyse, KPI, interprétation et recommandations
```

Matomo pourra fournir :

- visites ;
- visiteurs uniques ;
- pages vues ;
- événements ;
- durée moyenne ;
- taux de rebond ;
- visiteurs récurrents ;
- top pages.

Mais Matomo ne remplace pas les données de référence nécessaires :

- population éligible ;
- mapping organisationnel ;
- dictionnaire métier ;
- seuils métier.

---

## 17. Roadmap courte

### Phase 1 — Stabilisation

- Dashboard adoption unifié
- KPI communs
- Interprétations par bloc
- Documentation du modèle commun
- Documentation des données à demander

### Phase 2 — Assistant V2

- Détection service dans la question
- Détection KPI
- Réponses multi-services
- Comparaison Booking / Learning Center
- Explication des limites de données

### Phase 3 — KPI avancés

- Stickiness DAU / MAU
- WAU / MAU
- variation période précédente
- signaux exploratoires de baisse
- analyse par campus / entité lorsque disponible

### Phase 4 — LLM

- moteur d’interprétation modulaire
- LLM optionnel
- fallback par règles
- prompts contrôlés
- données agrégées uniquement

### Phase 5 — Sources dynamiques

- expérimentation Matomo API
- intégration d’une nouvelle application web
- transformation vers modèle commun
- extension du dashboard

---

## 18. Bonnes pratiques du projet

Pendant le développement :

- faire des petits commits ;
- tester après chaque modification ;
- éviter les gros refactors automatiques ;
- ne pas inventer de données ;
- ne pas exposer de données sensibles ;
- garder les KPI calculés par Python ;
- garder l’IA dans la couche d’interprétation ;
- documenter les limites.

Commandes utiles :

```powershell
git status
python -m pytest
python -m streamlit run app.py
git add .
git commit -m "message clair"
git push
```

---

## 19. État actuel

État actuel du projet :

```text
Dashboard adoption unifié terminé
Interprétations contextuelles par bloc ajoutées
Learning Center intégré
Booking intégré
Qualité des données affichée
Documentation common data model créée
Documentation data requests créée
Tests automatisés OK
```

---

## 20. Conclusion

AI Adoption Assistant est un POC orienté décision qui combine :

- data analytics ;
- KPI d’adoption ;
- dashboard interactif ;
- interprétation contrôlée des résultats ;
- préparation à l’intégration LLM ;
- préparation à l’intégration de nouvelles sources comme Matomo ou Microsoft Graph.

L’objectif final est de fournir aux responsables IT une vue centralisée, fiable et interprétable de l’adoption des services numériques.
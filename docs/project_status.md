# Project Status — AI Adoption Assistant

## 1. Objectif du projet

Le projet **AI Adoption Assistant** vise à concevoir une solution d’analyse de l’adoption et de l’utilisation des services numériques en entreprise.

L’objectif est de fournir aux responsables IT :

- un dashboard centralisé de suivi de l’adoption ;
- des KPI d’usage fiables ;
- une lecture par service, période, campus ou entité ;
- des interprétations contextuelles des résultats ;
- une base pour un futur assistant IA conversationnel connecté aux indicateurs.

---

## 2. Position actuelle

Le projet est actuellement au stade de **POC avancé**.

La version actuelle permet déjà d’analyser plusieurs services numériques dans un même dashboard unifié.

Services actuellement intégrés :

- Learning Center
- Booking

L’objectif actuel n’est plus seulement de créer des visualisations séparées, mais de construire une base réutilisable pour plusieurs applications.

---

## 3. Ce qui est déjà réalisé

### Dashboard adoption unifié

Un onglet principal **Dashboard adoption** a été créé.

Il regroupe les indicateurs communs pour plusieurs services.

Sections disponibles :

| Section | Statut |
|---|---|
| Vue d’ensemble KPI | Terminé |
| Évolution de l’adoption | Terminé |
| Usage par entité / campus | Terminé |
| Top interactions | Terminé |
| Données manquantes / Qualité des données | Terminé |
| Popovers d’interprétation par bloc | Terminé |

---

## 4. KPI actuellement calculés

Les indicateurs suivants sont disponibles :

| KPI | Description | Statut |
|---|---|---|
| DAU | Utilisateurs actifs quotidiens | Disponible |
| WAU | Utilisateurs actifs hebdomadaires | Disponible |
| MAU | Utilisateurs actifs mensuels | Disponible |
| Fréquence moyenne | Événements moyens par utilisateur actif | Disponible |
| Événements | Volume total d’actions observées | Disponible |
| Usage par service | Comparaison multi-services | Disponible |
| Usage par campus / entité | Disponible lorsque la donnée existe | Partiel |
| Taux d’utilisation | Actifs / population éligible | Non calculable actuellement |

Point important :

```text
Les KPI actuels mesurent l’usage observé.
Le taux d’adoption réel nécessite la population éligible.
```

---

## 5. Données intégrées

### 5.1 Learning Center

Source exploitée :

- logs web ;
- routes ;
- pages ;
- API ;
- utilisateurs observés ;
- statuts HTTP ;
- sessions lorsque disponibles.

Analyses possibles :

- DAU ;
- WAU ;
- MAU ;
- fréquence moyenne ;
- évolution temporelle ;
- top routes/pages/API ;
- erreurs et éléments techniques.

Limite principale :

```text
Le mapping utilisateur vers entité, campus ou direction est manquant.
```

---

### 5.2 Booking

Source exploitée :

- événements applicatifs ;
- actions métier ;
- utilisateurs observés ;
- campus ;
- dates d’activité.

Analyses possibles :

- DAU ;
- WAU ;
- MAU ;
- fréquence moyenne ;
- évolution temporelle ;
- usage par campus ;
- top actions métier.

Exemples d’actions observées :

```text
UPDATE_GUEST
UPDATE_GUEST_REQUEST
CREATE_HOUSING
ASSIGN_ROOM
```

Limite principale :

```text
La population éligible par service ou campus est manquante.
```

---

## 6. Interprétations contextuelles

Chaque bloc principal du Dashboard adoption contient maintenant un popover :

```text
💡 Interprétation IA
```

Chaque popover fournit :

1. une observation ;
2. une interprétation ;
3. une recommandation.

Sections couvertes :

| Bloc | Interprétation disponible |
|---|---|
| KPI communs | Oui |
| Évolution de l’adoption | Oui |
| Usage par entité / campus | Oui |
| Top interactions | Oui |
| Qualité des données | Oui |

Les interprétations actuelles sont générées par des règles contrôlées à partir des KPI calculés et des données disponibles.

Le LLM n’est pas encore branché.

Principe conservé :

```text
Python calcule les KPI.
L’IA interprète les résultats.
Le LLM ne doit pas calculer les indicateurs.
```

---

## 7. Documentation créée

Le dossier `docs/` contient actuellement :

| Document | Rôle |
|---|---|
| `common_data_model.md` | Décrit le modèle de données commun |
| `data_requests.md` | Liste les données à demander pour améliorer l’analyse |
| `project_status.md` | Résume l’état actuel du projet |

Ces documents servent à :

- préparer les réunions ;
- expliquer l’architecture ;
- alimenter le rapport final ;
- justifier les choix techniques ;
- cadrer les prochaines demandes de données.

---

## 8. Modèle de données commun

Le projet repose sur un modèle de données commun permettant d’intégrer plusieurs applications.

Champs principaux :

| Champ | Description |
|---|---|
| `event_timestamp` | Date et heure de l’événement |
| `user_id` | Identifiant utilisateur anonymisé ou technique |
| `service` | Service numérique concerné |
| `action` | Action ou événement observé |
| `department` | Entité, campus ou direction si disponible |
| `source` | Origine technique de la donnée |
| `session_id` | Identifiant de session si disponible |
| `metadata` | Informations complémentaires |

Pipeline logique :

```text
Source brute
→ Extraction
→ Nettoyage / normalisation
→ Modèle commun
→ Calcul KPI
→ Dashboard adoption
→ Interprétation / recommandation
```

---

## 9. Qualité des données

La version actuelle distingue clairement :

| Situation | Affichage |
|---|---|
| Donnée absente | `Non renseigné` |
| Population éligible absente | `Manquante` |
| Taux impossible à calculer | `Non calculable` |
| Données incomplètes | `Partiel` ou `À compléter` |

Cette approche évite d’inventer des valeurs et permet de garder une analyse fiable.

---

## 10. Limites actuelles

Les principales limites actuelles sont :

| Limite | Impact |
|---|---|
| Population éligible manquante | Taux d’utilisation réel non calculable |
| Mapping entité/campus incomplet | Analyse organisationnelle partielle |
| Dictionnaire métier incomplet | Certaines actions applicatives restent difficiles à interpréter |
| Seuils métier non validés | Les alertes de sous-utilisation restent exploratoires |
| Calendrier métier absent | Les pics ou baisses sont difficiles à expliquer précisément |
| LLM non encore intégré | Les interprétations restent basées sur règles contrôlées |

Conclusion actuelle :

```text
Le dashboard mesure correctement l’usage observé.
Pour mesurer l’adoption métier complète, il faut compléter les données de référence.
```

---

## 11. Données à demander

Données prioritaires à demander à l’équipe :

1. population éligible par service ;
2. mapping anonymisé utilisateur vers entité, campus ou direction ;
3. dictionnaire des actions métier ;
4. liste officielle des services à analyser ;
5. seuils métier pour qualifier une baisse ou une sous-utilisation ;
6. calendrier métier : incidents, campagnes, maintenances, événements.

Demande minimale pour débloquer la suite :

```text
Population éligible + mapping utilisateur + dictionnaire actions métier.
```

---

## 12. État technique

Branche de travail actuelle :

```text
feature/unified-dashboard
```

Version sécurisée précédente :

```text
v1-dashboard-presented-2026-07-30
```

Commandes principales :

```powershell
python -m pytest
python -m streamlit run app.py
```

État attendu des tests :

```text
61 passed
```

Warnings connus :

| Warning | Impact |
|---|---|
| Pandas date parsing | Non bloquant actuellement |
| Pytest cache / OneDrive permissions | Non bloquant actuellement |

---

## 13. Derniers commits importants

Travaux récents réalisés :

| Travail | Statut |
|---|---|
| Dashboard adoption unifié | Terminé |
| Suppression / masquage onglet Architecture | Terminé |
| Tableau Usage par entité / campus | Terminé |
| Tableau Top interactions | Terminé |
| Bloc Qualité des données | Terminé |
| Popover KPI | Terminé |
| Popover Évolution | Terminé |
| Popover Usage par entité / campus | Terminé |
| Popover Top interactions | Terminé |
| Popover Qualité des données | Terminé |
| Documentation modèle commun | Terminé |
| Documentation données à demander | Terminé |
| README projet | Terminé |

---

## 14. Prochaines étapes recommandées

### Priorité 1 — Assistant V2

Améliorer l’assistant pour répondre à des questions ciblées.

Fonctionnalités attendues :

- détecter le service demandé ;
- détecter le KPI demandé ;
- répondre sur Booking ;
- répondre sur Learning Center ;
- comparer deux services ;
- expliquer les limites de données.

Questions cibles :

```text
Quel est le MAU de Booking ?
Quel est le DAU du Learning Center ?
Compare Booking et Learning Center.
Quel campus utilise le plus Booking ?
Pourquoi le taux d’utilisation est non calculable ?
Quelles données manquent pour mesurer l’adoption réelle ?
```

---

### Priorité 2 — KPI avancés

Ajouter des indicateurs complémentaires :

| KPI | Description |
|---|---|
| Stickiness | DAU / MAU |
| WAU / MAU | Récurrence hebdomadaire |
| Variation période précédente | Hausse ou baisse d’usage |
| Part par service | Répartition multi-services |
| Signaux exploratoires de baisse | Détection prudente des anomalies |

---

### Priorité 3 — Architecture LLM propre

Préparer une couche dédiée pour les interprétations.

Architecture cible :

```text
Dashboard
→ Contexte structuré
→ RuleBasedInsightEngine
→ LLMInsightEngine optionnel
→ Popover / Assistant IA
```

Principe :

```text
Le moteur par règles reste le fallback.
Le LLM enrichit la formulation, mais ne calcule pas les KPI.
```

---

### Priorité 4 — Matomo comme source dynamique

Matomo sera utilisé comme source web analytics future.

Positionnement :

```text
Matomo = source de collecte
Dashboard = couche d’analyse et d’interprétation
```

Étapes futures :

1. installer Matomo localement ;
2. connecter une petite application web de test ;
3. générer des visites et événements ;
4. extraire les données via API ;
5. transformer les données vers le modèle commun ;
6. afficher les résultats dans le dashboard.

---

### Priorité 5 — Recommandations et alertes

Les recommandations existent déjà sous forme contrôlée dans les popovers.

Les alertes fortes nécessitent encore :

- seuils métier ;
- population éligible ;
- historique suffisant ;
- validation encadrante ou équipe métier.

Pour l’instant, les alertes doivent rester exploratoires.

---

## 15. Décisions importantes

Décisions validées dans la direction actuelle du projet :

| Décision | Justification |
|---|---|
| Dashboard unifié | Éviter des dashboards séparés par service |
| Modèle de données commun | Rendre le système extensible |
| Données manquantes visibles | Éviter les conclusions fausses |
| Interprétations par bloc | Rendre chaque visualisation actionnable |
| LLM plus tard | Stabiliser d’abord les KPI et l’interface |
| Matomo comme source | Ne pas remplacer le dashboard par Matomo |
| Security Analytics secondaire | Garder comme bonus, pas priorité principale |

---

## 16. Risques identifiés

| Risque | Mesure de réduction |
|---|---|
| Données incomplètes | Afficher `Non calculable` / `Non renseigné` |
| Mauvaise interprétation métier | Demander dictionnaire actions et seuils |
| Trop de features non stabilisées | Développer par petites étapes |
| LLM hallucine | Utiliser données agrégées + fallback règles |
| Données sensibles | Anonymisation et agrégation |
| Refactor risqué | Commits courts et tests après chaque changement |

---

## 17. Synthèse courte pour réunion

Version courte à présenter :

```text
Le POC actuel dispose maintenant d’un Dashboard adoption unifié permettant d’analyser Learning Center et Booking dans une même logique. Les KPI principaux sont disponibles : DAU, WAU, MAU, fréquence moyenne, évolution temporelle, usage par campus/entité lorsque disponible, top interactions et qualité des données. Chaque bloc du dashboard contient une interprétation contextuelle avec observation, interprétation et recommandation.

La solution mesure aujourd’hui l’usage observé. Pour passer à une mesure complète de l’adoption métier, il faut compléter les données de référence : population éligible, mapping utilisateur vers entité/campus/direction, dictionnaire des actions métier et seuils de sous-utilisation.

Les prochaines étapes sont l’amélioration de l’assistant IA, l’ajout de KPI avancés, puis l’intégration progressive d’un LLM et de sources dynamiques comme Matomo.
```

---

## 18. Conclusion

Le projet dispose maintenant d’une base solide :

- dashboard centralisé ;
- modèle de données commun ;
- KPI d’adoption ;
- interprétations par bloc ;
- documentation technique ;
- liste claire des données manquantes ;
- stratégie d’évolution vers assistant IA et LLM.

La priorité suivante est d’améliorer l’assistant pour qu’il réponde correctement aux questions métier sur les services, les KPI et les limites de données.
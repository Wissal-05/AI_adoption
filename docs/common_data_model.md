# Common Data Model — Adoption Analytics

## 1. Objectif

Le modèle de données commun permet d’analyser plusieurs services numériques avec une structure unique.

L’objectif est d’éviter un dashboard séparé pour chaque application et de construire une vue centralisée de l’adoption numérique.

Chaque source de données est transformée vers un format commun avant le calcul des KPI.

Exemples de services actuellement intégrés :

- Learning Center
- Booking

Exemples de sources possibles :

- logs web Nginx
- événements applicatifs
- exports CSV/Excel
- API analytics
- Matomo API
- Microsoft Graph API

---

## 2. Principe général

Chaque application peut avoir une structure technique différente, mais elle doit être convertie vers un schéma commun.

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

## 3. Champs communs principaux

| Champ | Description | Exemple | Obligatoire |
|---|---|---|---|
| `event_timestamp` | Date et heure de l’événement | `2026-07-23 10:15:00` | Oui |
| `user_id` | Identifiant utilisateur anonymisé ou technique | `user_123` | Oui |
| `service` | Nom du service numérique | `Learning Center`, `Booking` | Oui |
| `action` | Action ou événement utilisateur | `visit`, `page_view`, `UPDATE_GUEST` | Oui |
| `department` | Entité, campus ou direction | `Benguerir`, `Rabat`, `Non renseigné` | Optionnel |
| `source` | Origine technique de la donnée | `nginx_logs`, `booking_export`, `matomo_api` | Optionnel |
| `session_id` | Identifiant de session si disponible | `session_001` | Optionnel |
| `metadata` | Informations complémentaires | route, status, device, etc. | Optionnel |

---

## 4. Champs dérivés pour les KPI

| Champ dérivé | Description |
|---|---|
| `date` | Date extraite de `event_timestamp` |
| `month` | Mois d’analyse |
| `week` | Semaine d’analyse |
| `is_active_user` | Indique si l’utilisateur est actif sur la période |
| `events_count` | Nombre total d’événements |
| `active_users` | Nombre d’utilisateurs actifs uniques |
| `avg_events_per_user` | Fréquence moyenne d’utilisation |

---

## 5. KPI calculés

| KPI | Définition |
|---|---|
| DAU | Nombre d’utilisateurs actifs uniques sur une journée |
| WAU | Nombre d’utilisateurs actifs uniques sur 7 jours |
| MAU | Nombre d’utilisateurs actifs uniques sur 30 jours ou sur le mois |
| Fréquence moyenne | Nombre moyen d’événements par utilisateur actif |
| Événements | Volume total d’actions ou événements observés |
| Part d’usage | Part des utilisateurs ou événements par service, entité ou interaction |
| Taux d’utilisation | Utilisateurs actifs / population éligible |

---

## 6. Données nécessaires pour mesurer l’adoption complète

Les données actuellement disponibles permettent de mesurer l’usage observé.

Pour mesurer une adoption métier complète, certaines données de référence sont nécessaires.

| Donnée nécessaire | Utilité | Statut actuel |
|---|---|---|
| Population éligible par service | Calculer le taux d’utilisation réel | Manquante |
| Mapping utilisateur vers entité/campus/direction | Analyser l’adoption par organisation | Partiellement disponible |
| Dictionnaire des actions métier | Comprendre la signification des actions applicatives | À compléter |
| Seuils métier d’adoption | Définir sous-utilisation, alertes et recommandations | À valider |
| Calendrier métier | Expliquer les pics ou baisses d’usage | À collecter |

---

## 7. Exemple de mapping — Learning Center

| Donnée source | Champ commun | Remarque |
|---|---|---|
| `event_time_utc` | `event_timestamp` | Horodatage de l’événement |
| `user_id` | `user_id` | Identifiant utilisateur |
| `page` | `action` ou `metadata.page` | Page, route ou endpoint visité |
| `service` | `service` | Learning Center |
| `status` | `metadata.status` | Code HTTP |
| `sessions` | `session_id` ou métrique session | Disponible selon le traitement |
| Entité/campus | `department` | Non renseigné actuellement |

Limite principale :

```text
Le Learning Center dispose de données d’usage web, mais le mapping utilisateur vers entité/campus est manquant.
```

---

## 8. Exemple de mapping — Booking

| Donnée source | Champ commun | Remarque |
|---|---|---|
| Timestamp événement | `event_timestamp` | Date de l’action |
| Utilisateur | `user_id` | Identifiant utilisateur |
| Action métier | `action` | Exemple : UPDATE_GUEST |
| Service | `service` | Booking |
| Campus | `department` | Benguerir, Rabat, Khouribga, Casablanca |

Limite principale :

```text
Booking dispose d’une répartition par campus, mais la population éligible reste manquante.
```

---

## 9. Gestion des données manquantes

Le dashboard distingue clairement les données calculables et non calculables.

| Cas | Affichage |
|---|---|
| Entité ou campus manquant | `Non renseigné` |
| Population éligible absente | `Manquante` |
| Taux d’utilisation impossible | `Non calculable` |
| Données partielles | `Partiel` ou `À compléter` |

Cette approche évite d’inventer des valeurs et permet de garder une lecture fiable du dashboard.

---

## 10. Matomo dans l’architecture

Matomo n’est pas considéré comme un service métier à analyser.

Matomo est une source de collecte web analytics.

Exemple :

```text
Service analysé : site web Learning Center
Source de données possible : Matomo API
```

Les données Matomo peuvent être transformées vers le modèle commun :

| Donnée Matomo | Champ commun |
|---|---|
| Visits | événements ou sessions |
| Unique visitors | utilisateurs actifs |
| Page URL | action ou metadata.page |
| Events | action |
| Date | event_timestamp |
| Site name | service |

---

## 11. Position actuelle du projet

État actuel :

- Dashboard adoption unifié créé
- Learning Center intégré
- Booking intégré
- KPI communs calculés
- Graphique d’évolution commun ajouté
- Usage par entité/campus ajouté
- Top interactions ajouté
- Qualité des données ajoutée
- Interprétations contextuelles par bloc ajoutées

Limites actuelles :

- Population éligible manquante
- Mapping entité/campus incomplet pour Learning Center
- Seuils métier non encore validés
- Dictionnaire des actions métier à compléter

---

## 12. Prochaine étape

La prochaine étape consiste à consolider les données de référence nécessaires :

1. population éligible par service ;
2. mapping utilisateur vers entité, campus ou direction ;
3. dictionnaire des actions métier ;
4. seuils métier pour les alertes et recommandations ;
5. calendrier métier pour contextualiser les variations.

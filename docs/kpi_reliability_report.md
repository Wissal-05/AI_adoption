# KPI Reliability Report

## Résumé des audits par service

| KPI | Service | Source | Formula | Reference date | Status | Notes |
|---|---|---|---|---|---|---|
| DAU/WAU/MAU | Booking | daily-kpis-60d.csv | Session / Login aggregation | 2026-07-23 | PARTIAL | Décalage (368 vs 161) dû au périmètre mesuré (events vs logins) et offset UTC+2. |
| DAU/WAU/MAU | Learning Center | nginx-events.csv | `users in [ref_date - X, ref_date]` | 2026-07-17 | CERTIFIED | Parfaite cohérence avec le moteur. |
| DAU/WAU/MAU | Ecommerce Demo | Matomo Raw (live_actions) | `users in [ref_date - X, ref_date]` | 2026-08-09 | CERTIFIED | Aucune perte de données réelle, le mismatch était lié à des runs d'export différents. |
| DAU/WAU/MAU | Tous les services | Dashboard Global | `nunique(user_id)` global | max(date) | INVALID | Addition de namespaces hétérogènes + Glitch de fraîcheur temporelle. |

---

## A. Booking : Explication 161 vs 368
* **MAU dynamic (161)** : Issu exclusivement des `usage-events-60d.csv` sans décalage horaire, comptant uniquement les utilisateurs ayant déclenché une action métier sur 30 jours.
* **MAU daily-kpis (368)** : Ce KPI pré-calculé compte les utilisateurs ayant eu une session *active* (y compris persistante sans action) ou ayant créé un compte, et intègre un décalage de Timezone (+2h). La preuve mathématique est qu'en agrégeant `usage_events`, `sessions`, et `users_dimension` avec un offset de +2h, le DAU retombe exactement sur 14.
* **Root Cause** : `daily-kpis-60d.csv` est vraisemblablement un export externe consolidé mesurant le 'Login Activity' ou 'Session Activity' (Trafic global) alors que `usage-events` mesure l''Action Activity' (Actions métier pures).
* **Recommended Source of Truth** : **UNRESOLVED**. Dépend si le métier veut mesurer l'usage passif (connexions = 368) ou actif (actions = 161).

## B. Booking : 252 Lignes Rejetées
Lors de la normalisation initiale par `normalize_usage_events`, avec un parsing de date par défaut (sans `format=mixed`), exactement 252 lignes sont rejetées car leur format date (`%Y-%m-%d %H:%M:%S.%f`) échoue silencieusement.

| Reason | Rows |
|---|---|
| missing user_id | 0 |
| invalid timestamp | 252 |
| both missing | 0 |
| other | 0 |

*(Les 252 lignes sont des événements standards où l'heure inclut des millisecondes qui n'ont pas été castées proprement en DateTime).*

## C. Matomo Ecommerce : Validation 74 vs 22
Les fichiers sources sont de la forme `live_actions_TIMESTAMP.csv`.
L'audit comparait le premier export brut chronologique (`20260806_222122` = 74 lignes) contre le dernier export processé par le registry (`20260809_153600` = 22 lignes).
* RAW actions du run 153511 = 22
* NORMALIZED events du run 153600 = 22
* Dropped events = 0
* **Statut = OK**, aucune perte d'événement entre le fichier brut et le fichier processé d'un même run.

## D. Learning Center : Explication 3 789 996 -> 1 407 875
Le pipeline nginx-events filtre massivement en aval. Le waterfall réel est le suivant (approximation basée sur la logique `analytics_eligible`) :

Raw Nginx rows | 3 789 996
--- | ---
- static resources & bots (non analytics eligible) | - 2 382 121
- missing user_id / invalid timestamp | 0
**= final usage_events** | **1 407 875**

## E. Global View : Certification Architecturale
Nous certifions formellement que :
1. L'opération `nunique(user_id)` sur l'agrégat (Booking + Learning Center + Ecommerce) est mathématiquement et logiquement **INVALIDE** car les `user_id` ne sont pas réconciliés (pas de Cross-ID unique).
2. L'utilisation de `max(event_timestamp)` comme date de référence globale provoque un **biais de fraîcheur critique**. Si Matomo est à jour (9 Août) mais Learning Center s'arrête le 17 Juillet, calculer un KPI 30 jours depuis le 9 Août fait virtuellement "disparaître" tous les utilisateurs du Learning Center antérieurs au 10 Juillet.

**Recommandation d'Architecture** :
* Quand `Service != "Tous les services"` : Calculer DAU/WAU/MAU dynamiquement, utiliser la `reference_date` propre au service, afficher cette date de fraîcheur.
* Quand `Service == "Tous les services"` : **NE PAS** calculer ni afficher de métrique utilisateur unique. Afficher uniquement les KPI service par service, et indiquer la fraîcheur individuelle de chaque source de données.

# Data Requests — Adoption Analytics

## 1. Objectif

Ce document liste les données nécessaires pour améliorer l’analyse de l’adoption des services numériques.

Le dashboard actuel permet déjà de mesurer l’usage observé :

- utilisateurs actifs ;
- DAU / WAU / MAU ;
- fréquence moyenne ;
- évolution temporelle ;
- usage par service ;
- usage par entité ou campus lorsque la donnée est disponible ;
- top interactions ;
- qualité des données disponibles.

Cependant, certaines données de référence sont nécessaires pour passer d’une analyse d’usage observé à une vraie analyse d’adoption métier.

---

## 2. Principe important

Les logs et événements applicatifs montrent ce que les utilisateurs ont fait.

Mais pour mesurer l’adoption réelle, il faut aussi savoir :

- qui était censé utiliser le service ;
- à quelle entité, campus ou direction appartient l’utilisateur ;
- quelles actions sont importantes métier ;
- quels seuils permettent de dire qu’un service est sous-utilisé ;
- quels événements métier ou techniques peuvent expliquer les variations.

Sans ces données, le dashboard reste fiable, mais certaines conclusions doivent rester prudentes.

---

## 3. État actuel

### Données actuellement exploitables

| Service | Données disponibles | Analyse possible |
|---|---|---|
| Learning Center | Logs web / routes / API / utilisateurs observés | DAU, WAU, MAU, fréquence, évolution, top routes |
| Booking | Événements applicatifs / actions métier / campus | DAU, WAU, MAU, fréquence, évolution, usage par campus, top actions |

### Limites actuelles

| Limite | Impact |
|---|---|
| Population éligible manquante | Le taux d’utilisation réel n’est pas calculable |
| Mapping entité/campus incomplet pour certains services | L’analyse par organisation reste partielle |
| Dictionnaire des actions métier incomplet | Certaines actions sont difficiles à interpréter |
| Seuils métier non validés | Les alertes de sous-utilisation ne peuvent pas être considérées comme définitives |
| Calendrier métier absent | Les pics ou baisses d’usage sont difficiles à expliquer |

---

## 4. Priorités des données à demander

## Priorité 1 — Données indispensables

Ces données sont nécessaires pour calculer un vrai taux d’adoption et fiabiliser les analyses.

| Donnée | Pourquoi elle est nécessaire | Format souhaité | Priorité |
|---|---|---|---|
| Population éligible par service | Calculer le taux d’utilisation réel | CSV / Excel / extraction SQL | P1 |
| Mapping utilisateur vers entité/campus/direction | Analyser l’adoption par organisation | CSV / Excel / annuaire / AD export | P1 |
| Liste des services à analyser | Définir le périmètre officiel | Excel / document de cadrage | P1 |
| Dictionnaire des actions métier | Comprendre les événements applicatifs | Excel / documentation applicative | P1 |

---

## Priorité 2 — Données importantes pour les recommandations

Ces données permettent d’améliorer les interprétations et de générer des recommandations plus pertinentes.

| Donnée | Pourquoi elle est nécessaire | Format souhaité | Priorité |
|---|---|---|---|
| Seuils métier d’adoption | Définir sous-utilisation, baisse significative, alerte | Document métier / validation encadrante | P2 |
| Calendrier métier | Expliquer les variations : vacances, examens, campagnes, incidents | Excel / calendrier / notes internes | P2 |
| Historique sur plusieurs mois | Comparer les périodes et détecter les tendances | Logs / exports mensuels | P2 |
| Liste des incidents techniques | Corréler les baisses d’usage avec les problèmes techniques | Export monitoring / ticketing | P2 |

---

## Priorité 3 — Données pour extension future

Ces données peuvent être intégrées après stabilisation du dashboard principal.

| Donnée | Utilité | Format souhaité | Priorité |
|---|---|---|---|
| Matomo API | Source dynamique pour web analytics | API token / export API | P3 |
| Microsoft Graph API | Analyse Microsoft 365 : Teams, SharePoint, Outlook | Accès API / exports | P3 |
| Données VPN | Analyse des connexions distantes | Logs / exports | P3 |
| Outils de supervision | Corrélation adoption / disponibilité | API / exports | P3 |
| Power BI dataset | Intégration ou comparaison avec reporting existant | Dataset / export | P3 |

---

## 5. Données détaillées à demander

## 5.1 Population éligible par service

### Objectif

Calculer le taux d’utilisation réel.

Formule :

```text
Taux d’utilisation = utilisateurs actifs / population éligible × 100
```

### Champs souhaités

| Champ | Description | Exemple |
|---|---|---|
| `service` | Nom du service numérique | `Learning Center` |
| `period` | Période concernée | `2026-07` |
| `eligible_users` | Nombre d’utilisateurs censés utiliser le service | `10000` |
| `entity` | Direction ou entité si disponible | `IT` |
| `campus` | Campus si disponible | `Benguerir` |
| `profile` | Type utilisateur si disponible | `student`, `staff`, `teacher` |

### Format souhaité

```csv
service,period,entity,campus,profile,eligible_users
Learning Center,2026-07,Non renseigné,Non renseigné,students,10000
Booking,2026-07,Non renseigné,Benguerir,staff,200
```

### Impact dans le dashboard

Cette donnée permettra d’afficher :

- taux d’utilisation global ;
- taux d’utilisation par service ;
- taux d’utilisation par campus ;
- taux d’utilisation par entité ;
- détection de services sous-utilisés.

---

## 5.2 Mapping utilisateur vers entité / campus / direction

### Objectif

Relier les événements d’usage aux structures organisationnelles.

### Champs souhaités

| Champ | Description | Exemple |
|---|---|---|
| `user_id` | Identifiant utilisé dans les logs ou événements | `user_123` |
| `entity` | Entité ou direction | `Direction IT` |
| `campus` | Campus | `Rabat` |
| `department` | Département si disponible | `Digital Factory` |
| `profile` | Type utilisateur | `student`, `staff`, `teacher` |
| `status` | Statut du compte | `active`, `inactive` |

### Format souhaité

```csv
user_id,entity,campus,department,profile,status
user_123,Direction IT,Rabat,Digital Factory,staff,active
user_456,Learning Center,Benguerir,Education,student,active
```

### Impact dans le dashboard

Cette donnée permettra de répondre à des questions comme :

- quel campus utilise le plus un service ?
- quelle direction utilise le moins un service ?
- quels profils sont les plus actifs ?
- quels utilisateurs éligibles ne sont pas actifs ?

---

## 5.3 Dictionnaire des actions métier

### Objectif

Comprendre la signification des événements applicatifs.

Exemple actuel :

```text
UPDATE_GUEST
UPDATE_GUEST_REQUEST
CREATE_HOUSING
ASSIGN_ROOM
```

Ces actions sont visibles dans les données, mais leur signification métier doit être validée.

### Champs souhaités

| Champ | Description | Exemple |
|---|---|---|
| `service` | Service concerné | `Booking` |
| `action` | Nom technique de l’action | `UPDATE_GUEST` |
| `business_meaning` | Signification métier | `Modification des informations invité` |
| `action_type` | Type d’action | `create`, `update`, `view`, `delete` |
| `is_critical` | Action critique ou non | `yes`, `no` |
| `expected_frequency` | Fréquence attendue | `daily`, `weekly`, `occasional` |

### Format souhaité

```csv
service,action,business_meaning,action_type,is_critical,expected_frequency
Booking,UPDATE_GUEST,Modification des informations invité,update,yes,daily
Booking,CREATE_HOUSING,Création d’un logement,create,yes,occasional
```

### Impact dans le dashboard

Cette donnée permettra de produire des interprétations plus fiables :

- identifier les actions critiques ;
- détecter les actions sous-utilisées ;
- repérer les parcours répétitifs ;
- proposer des recommandations métier.

---

## 5.4 Liste officielle des services à analyser

### Objectif

Définir le périmètre officiel du projet.

### Champs souhaités

| Champ | Description | Exemple |
|---|---|---|
| `service` | Nom du service | `Learning Center` |
| `type` | Type de service | `web app`, `platform`, `M365`, `VPN` |
| `owner` | Équipe ou responsable | `IT / Digital` |
| `data_source` | Source de données disponible | `nginx_logs`, `api`, `csv`, `matomo` |
| `priority` | Priorité d’intégration | `P1`, `P2`, `P3` |
| `status` | Statut d’accès | `available`, `pending`, `not available` |

### Format souhaité

```csv
service,type,owner,data_source,priority,status
Learning Center,web app,IT,nginx_logs,P1,available
Booking,platform,IT,csv_export,P1,available
Microsoft Teams,M365,IT,microsoft_graph,P2,pending
```

### Impact dans le dashboard

Cette donnée permettra de structurer la roadmap d’intégration des services.

---

## 5.5 Seuils métier d’adoption

### Objectif

Définir les règles permettant d’identifier :

- service sous-utilisé ;
- baisse d’adoption ;
- adoption faible par campus ;
- action métier anormalement faible ;
- alerte significative.

### Exemples de seuils à valider

| Règle | Exemple |
|---|---|
| Service sous-utilisé | Taux d’utilisation inférieur à 30 % |
| Baisse significative | MAU en baisse de plus de 20 % sur un mois |
| Faible usage campus | Campus inférieur à la moyenne globale de 15 points |
| Forte concentration | Une interaction représente plus de 50 % des événements |
| Inactivité | Aucun événement sur 30 jours |

### Format souhaité

```csv
rule_name,service,kpi,threshold,period,description
underused_service,all,usage_rate,<30%,monthly,Service considéré comme sous-utilisé
significant_drop,all,mau,-20%,monthly,Baisse significative d’adoption
```

### Impact dans le dashboard

Ces seuils permettront de passer de simples observations à des alertes validées.

---

## 5.6 Calendrier métier et événements importants

### Objectif

Expliquer les variations d’usage.

Une baisse ou un pic peut être causé par :

- vacances ;
- examens ;
- rentrée universitaire ;
- campagne de communication ;
- nouvelle fonctionnalité ;
- incident technique ;
- maintenance ;
- changement d’accès ;
- migration applicative.

### Champs souhaités

| Champ | Description | Exemple |
|---|---|---|
| `date` | Date de l’événement | `2026-07-15` |
| `event_type` | Type d’événement | `incident`, `campaign`, `holiday` |
| `service` | Service concerné | `Learning Center` |
| `description` | Description courte | `Maintenance serveur` |
| `impact_expected` | Impact attendu | `baisse trafic`, `hausse usage` |

### Format souhaité

```csv
date,event_type,service,description,impact_expected
2026-07-15,incident,Learning Center,Maintenance serveur,baisse trafic
2026-07-20,campaign,Booking,Communication interne,hausse usage
```

### Impact dans le dashboard

Cette donnée permettra d’expliquer les ruptures de tendance et de produire des recommandations plus pertinentes.

---

## 6. Données demandées par service

## 6.1 Learning Center

| Donnée | Statut actuel | Besoin |
|---|---|---|
| Logs web | Disponible | Continuer l’exploitation |
| Pages / routes | Disponible | Classer pages métier / API / technique |
| Utilisateurs actifs | Disponible | Conserver identifiants anonymisés |
| Mapping entité/campus | Manquant | À fournir |
| Population éligible | Manquante | À fournir |
| Incidents / maintenance | Non disponible | À fournir si possible |
| Définition des pages critiques | Non disponible | À valider |

## 6.2 Booking

| Donnée | Statut actuel | Besoin |
|---|---|---|
| Événements applicatifs | Disponible | Continuer l’exploitation |
| Actions métier | Disponible techniquement | Besoin de dictionnaire métier |
| Campus | Disponible | À valider |
| Utilisateurs actifs | Disponible | Conserver identifiants anonymisés |
| Population éligible | Manquante | À fournir |
| Seuils métier | Non disponibles | À valider |
| Workflow métier | Non documenté | À documenter |

---

## 7. Format recommandé pour les échanges

Pour faciliter l’intégration, les données peuvent être fournies sous forme :

- CSV ;
- Excel ;
- export SQL ;
- API ;
- logs anonymisés ;
- documentation métier.

Format préféré pour le POC :

```text
CSV ou Excel anonymisé
```

Règles souhaitées :

- conserver un identifiant utilisateur stable mais anonymisé ;
- conserver les dates et heures ;
- éviter les noms/prénoms si non nécessaires ;
- fournir un dictionnaire des colonnes ;
- préciser la période couverte ;
- préciser la source technique.

---

## 8. Confidentialité et sécurité

Le projet peut fonctionner avec des données anonymisées.

Les données personnelles directes ne sont pas nécessaires pour le POC.

### À éviter

- noms complets ;
- emails personnels ;
- numéros de téléphone ;
- données sensibles inutiles ;
- contenu de messages ou documents.

### À privilégier

| Donnée réelle | Donnée anonymisée recommandée |
|---|---|
| email utilisateur | `user_id` stable |
| nom/prénom | non nécessaire |
| direction | conservée si utile |
| campus | conservé |
| rôle/profil | conservé |
| timestamp | conservé |
| action applicative | conservée |

Exemple :

```text
wissal.elbidali@example.com → user_001
```

---

## 9. Questions à poser à l’équipe

### Questions prioritaires

1. Quelle est la population éligible pour chaque service analysé ?
2. Peut-on avoir un mapping anonymisé `user_id → entité/campus/direction` ?
3. Quelles sont les applications prioritaires après Learning Center et Booking ?
4. Que signifient les actions métier Booking comme `UPDATE_GUEST` ?
5. Quels seuils permettent de dire qu’un service est sous-utilisé ?
6. Existe-t-il un calendrier des incidents, maintenances ou campagnes ?
7. Les données peuvent-elles être fournies périodiquement ?
8. Quelle source est préférée pour les sites web : logs, Matomo ou API applicative ?
9. Les utilisateurs doivent-ils être segmentés par étudiant, staff, enseignant ou autre profil ?
10. Quelles données ne doivent pas être exploitées pour des raisons de confidentialité ?

---

## 10. Demande minimale pour débloquer la suite

Pour améliorer rapidement le dashboard, la demande minimale est :

1. population éligible par service ;
2. mapping anonymisé utilisateur vers entité/campus/direction ;
3. dictionnaire des actions métier Booking ;
4. validation des services prioritaires ;
5. seuils métier simples pour les alertes.

---

## 11. Message court possible à envoyer

```text
Bonjour,

Pour améliorer l’analyse d’adoption et passer d’un usage observé à une mesure plus complète, j’aurais besoin si possible de quelques données de référence anonymisées :

1. la population éligible par service ;
2. le mapping utilisateur anonymisé vers entité/campus/direction ;
3. le dictionnaire des actions métier, notamment pour Booking ;
4. la liste des services prioritaires à intégrer ;
5. quelques seuils métier pour qualifier une baisse ou une sous-utilisation.

Ces éléments permettront de calculer le taux d’utilisation réel, fiabiliser l’analyse par organisation et produire des recommandations plus pertinentes.

Merci beaucoup.
```

---

## 12. Conclusion

Les données actuellement disponibles permettent de construire un dashboard solide d’usage observé.

Pour atteindre l’objectif complet du projet, il faut compléter ce socle avec des données de référence :

- population éligible ;
- mapping organisationnel ;
- dictionnaire métier ;
- seuils ;
- contexte temporel.

Ces données permettront de calculer des indicateurs d’adoption plus fiables, d’améliorer les recommandations et de préparer l’intégration future de sources dynamiques comme Matomo ou Microsoft Graph.
# Règles Méthodologiques

## Analyse Service par Service
Les KPI tels que le DAU, WAU et MAU doivent toujours être analysés de manière isolée pour chaque service. Il ne faut procéder à aucune agrégation multi-service pour compter les utilisateurs globaux, car les identités ne sont pas réconciliées entre les différentes sources de données.

## Calcul du Taux d'Adoption
Un taux d'adoption nécessite toujours deux éléments fondamentaux : le nombre d'utilisateurs actifs, rapporté au nombre de la population éligible.

## Agrégation Impossible pour Booking
Aucun taux d'adoption global pour l'ensemble du service Booking ne peut être obtenu en additionnant les populations éligibles de ses modules (Housing, Transport, etc.) car celles-ci peuvent se chevaucher de manière inconnue.

## Distinction Zéro et Indisponible
Dans nos analyses, la valeur `None`, `not_available` ou `telemetry_unavailable` ne signifie absolument pas zéro (0). Une absence de donnée reflète une limite technique ou méthodologique de la télémétrie, et non une inactivité.

## Périodes Silencieuses
Les jours silencieux internes (sans activité enregistrée) peuvent être représentés à 0 dans une série temporelle pour combler les trous. Toutefois, aucune donnée n'est fabriquée artificiellement en dehors de la couverture d'observation globale du dataset.

## Rôle du LLM
Le LLM (l'Intelligence Artificielle) ne calcule pas lui-même les KPI. Les fonctions Python (les tools) sont l'unique source de vérité. Le rôle du modèle est d'orchestrer les appels et d'expliquer les résultats.

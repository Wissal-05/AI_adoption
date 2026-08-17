# Limitations des Données

Ce document recense les limites méthodologiques et techniques qui affectent l'interprétation des données.

## Limitations Booking
- Certaines entités organisationnelles (comme le campus ou le département) peuvent être non renseignées, créant des actions orphelines limitant l'analyse granulaire.
- Des signatures événementielles répétées sont possibles dans les journaux. Elles ne constituent pas automatiquement des doublons confirmés en raison de l'absence d'un identifiant d'événement (`event_id`) unique, empêchant de prouver de manière irréfutable une duplication pure.
- **Transport** : La télémétrie métier est indisponible pour l'adoption. Par conséquent, le taux d'adoption est toujours "indisponible" et non pas "0 %".
- **Admin / Other** : La population éligible pour ces modules est indisponible, ce qui empêche de calculer certains taux d'adoption.

## Limitations Learning Center
- Certaines analyses de portée (Reach) reposent sur la métrique `source_ip` (l'adresse IP source).
- L'adresse IP source n'équivaut pas à un utilisateur authentifié unique. La présence de dispositifs comme le NAT, des proxies, ou des réseaux partagés peut introduire des biais et limiter la fiabilité absolue de l'interprétation du nombre réel d'utilisateurs.

## Limitations Ecommerce Demo
- Ne jamais présenter une intensité d'événements par utilisateur (events/user) comme une fréquence stratégique comparable entre services si cette dernière n'est pas structurellement ou explicitement disponible dans le modèle de données.
- Les dimensions organisationnelles (campus, départements) ne sont pas disponibles si aucun mapping fiable n'existe avec ce service.

## Limitations Multi-Service
- Les identités des utilisateurs ne sont pas réconciliées entre les différents services (Booking vs Learning Center vs Ecommerce Demo).
- Il n'est donc pas possible de calculer un DAU, WAU, ou MAU global à l'échelle de l'entreprise entière.
- Il est également impossible de calculer un taux d'adoption global arbitraire par agrégation de différents services.

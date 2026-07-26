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

Quel est le DAU ? DAU : 10 utilisateurs actifs.

Quel est le WAU ?WAU : 85 utilisateurs actifs.

Quel est le MAU ?MAU : 8,870 utilisateurs actifs.

Donne-moi les KPI d'adoption.KPI d’adoption :
DAU : 10
WAU : 85
MAU : 8,870

Donne-moi l'évolution sur 30 jours.Évolution sur 30 jours :
DAU : 666 → 10
WAU : 1,738 → 85
MAU : 2,929 → 8,877

Quelle est la fréquence d'utilisation ?Fréquence d’utilisation :
Utilisateurs actifs : 11,065
Événements totaux : 1,407,875
Événements moyens par utilisateur actif : 127.24
Jours actifs moyens par utilisateur : 1.11

Quel est le taux d'utilisation ?Taux d’utilisation : non calculable actuellement.
Le moteur KPI sait calculer ce taux, mais le référentiel des utilisateurs éligibles au service n’est pas disponible dans les données chargées.
Formule prévue : taux d’utilisation = utilisateurs actifs / utilisateurs éligibles × 100
Données nécessaires : référentiel RH, Active Directory, Azure AD, IAM ou matrice d’accès indiquant quels utilisateurs ont accès au service.

Quels sont les services sous-utilisés ?Services les moins utilisés:
service=Learning Center, active_users=11065, events=1407875, avg_events_per_active_user=127.24, underuse_reason=faible volume d'événements, faible nombre d'utilisateurs actifs, faible fréquence d'utilisation

Quelle direction utilise le plus le service ? Je peux répondre aux questions sur :

Les KPI d’adoption : DAU, WAU et MAU
L’évolution temporelle des KPI
La fréquence d’utilisation
Le taux d’utilisation et les données nécessaires pour le calculer
Les services les moins utilisés
L’usage par département
Les utilisateurs inactifs
Les routes suspectes (sécurité)
Exemples :

Quel est le DAU ?
Donne-moi les KPI d’adoption
Quelle est la fréquence d’utilisation ?
Quel est le taux d’utilisation ?
Quels sont les services sous-utilisés ?
Pour des réponses génératives plus avancées, activez le moteur LLM en définissant ASSISTANT_ENGINE=llm dans votre fichier .env.

Quels sont les utilisateurs inactifs ? Utilisateurs inactifs:

user_id=00f31c5ab65625e241dce511, department=Unknown, last_seen=2026-05-25 00:09:15, inactive_days=53
user_id=c2b98f979e9f105abed42a59, department=Unknown, last_seen=2026-05-25 01:43:20, inactive_days=53
user_id=8e222b04452f4848fe70f9a4, department=Unknown, last_seen=2026-05-25 04:44:19, inactive_days=53
user_id=e5db6486b279af9885e73f17, department=Unknown, last_seen=2026-05-25 07:09:47, inactive_days=53
user_id=f3f7201d8dfcf027fddc808f, department=Unknown, last_seen=2026-05-25 07:11:10, inactive_days=53
user_id=77f1b86246f3bf4a4ef7c5b7, department=Unknown, last_seen=2026-05-25 08:29:32, inactive_days=53
user_id=7c57eafe217a6195f0a5f8d4, department=Unknown, last_seen=2026-05-25 09:40:23, inactive_days=53
user_id=113654d70db530e5cc2a53fb, department=Unknown, last_seen=2026-05-25 09:59:47, inactive_days=53
user_id=3bc872fb7ddf6c0439e5c665, department=Unknown, last_seen=2026-05-25 10:06:11, inactive_days=53
user_id=a3bdf57aa057083d13b553ee, department=Unknown, last_seen=2026-05-25 11:11:52, inactive_days=53
Y a-t-il des routes suspectes ?Routes suspectes détectées:

event_timestamp=2026-07-10 13:48:01, source_ip=20.48.255.163, route=/adminfuns.php, status_code=404, user_agent=-, source=learning_center_nginx, event_id=2b87962b1edc1d46dbd662f263915b5a3e11d25c5d22d697c94d4a578506cd92, is_error=True, risk_label=Admin discovery
event_timestamp=2026-07-10 10:06:46, source_ip=134.122.124.74, route=/.git/config, status_code=404, user_agent=Mozilla/5.0 (X11; OpenBSD i386) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36, source=learning_center_nginx, event_id=8d367bf914ef1fed552ca90e4a147c7ea7152b853e9df003058b34dd4a2e33c4, is_error=True, risk_label=Secret/config probing
event_timestamp=2026-07-10 05:55:24, source_ip=20.48.255.163, route=/wp-admin/network/plugins.php, status_code=404, user_agent=-, source=learning_center_nginx, event_id=86be7c3a7ff3207bfc84104da48f4da2cd03c852c72794d8fc419395292c45c7, is_error=True, risk_label=CMS/admin probing
event_timestamp=2026-07-10 05:55:23, source_ip=20.48.255.163, route=/wp-admin/css/colors/sunrise, status_code=404, user_agent=-, source=learning_center_nginx, event_id=94442d5fa5e9f18621eddcb040395092986e96a3f58e9e56811795708bad2e13, is_error=True, risk_label=CMS/admin probing
event_timestamp=2026-07-10 05:55:23, source_ip=20.48.255.163, route=/wp-admin/css/colors/sunrise/, status_code=308, user_agent=-, source=learning_center_nginx, event_id=9060fb58ff9bfa6eb2c5a9eb79cb99e92412ed20dfa1b26754f94c0ad4e3b34e, is_error=False, risk_label=CMS/admin probing
event_timestamp=2026-07-10 05:55:17, source_ip=20.48.255.163, route=/admin.php, status_code=404, user_agent=-, source=learning_center_nginx, event_id=614b3ee4328ed749bf0da5d8aabbc243a12231ae06f32656b09ddf3016b8ed32, is_error=True, risk_label=Admin discovery
event_timestamp=2026-07-10 05:55:14, source_ip=20.48.255.163, route=/wp-admin/css/colors/blue, status_code=404, user_agent=-, source=learning_center_nginx, event_id=ceac198f8755df607f85ace18f5ec8b5b9137400d39fa301ba78e186a1db1160, is_error=True, risk_label=CMS/admin probing
event_timestamp=2026-07-10 05:55:14, source_ip=20.48.255.163, route=/wp-admin/css/colors/blue/, status_code=308, user_agent=-, source=learning_center_nginx, event_id=b68538a8b61e4176a400445638dfa0307e96b2e4c6092dd2fbcf5148e1753ac2, is_error=False, risk_label=CMS/admin probing
event_timestamp=2026-07-10 05:55:11, source_ip=20.48.255.163, route=/cgi-bin/admin.php, status_code=404, user_agent=-, source=learning_center_nginx, event_id=a488d46d0e1c72bfd97e086cc6d5ee80a5cd2f149b1d32728da49dc7ef0d4ea3, is_error=True, risk_label=Admin discovery
event_timestamp=2026-07-10 05:55:11, source_ip=20.48.255.163, route=/admin.php, status_code=308, user_agent=-, source=learning_center_nginx, event_id=099d0dec39056a9e205b77881d14700b45906c52d8befc427182c619ba1ada84, is_error=False, risk_label=Admin discovery



## Technologies utilisées

Python ;
Pandas ;
Streamlit ;
Plotly ;
Pytest ;
PowerShell ;
Groq / LLM optionnel ;
Microsoft Graph API prévu pour les futures sources.
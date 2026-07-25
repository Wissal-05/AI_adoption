"""Interface de stockage et spécifications SQL pour la migration future.

Ce module définit le contrat d'interface `StorageRepository` servant de passerelle
pour toute la persistance de l'application (événements, logs, KPIs).
Il documente également le schéma relationnel cible sous forme de commentaires
détaillés avec contraintes, clés et relations pour la future base SQL.
"""

from abc import ABC, abstractmethod
import pandas as pd


# ── SPÉCIFICATIONS ET MODÈLE SQL CIBLE ─────────────────────────────────────────
#
# Lors de la migration future vers un SGBDR (PostgreSQL, SQL Server, MySQL),
# les structures de données seront mappées sur le schéma relationnel suivant.
#
# 1. TABLE: services
#    Contient les services/applications dont on analyse l'adoption.
#    - id : INT AUTO_INCREMENT PRIMARY KEY
#    - name : VARCHAR(100) NOT NULL UNIQUE (ex: 'learning_center', 'booking')
#    - display_name : VARCHAR(150) NOT NULL
#
# 2. TABLE: departments
#    Contient la liste des départements/services des utilisateurs.
#    - id : INT AUTO_INCREMENT PRIMARY KEY
#    - name : VARCHAR(100) NOT NULL UNIQUE (ex: 'IT', 'RH', 'Finance')
#
# 3. TABLE: users
#    Contient les utilisateurs uniques anonymisés.
#    - id : VARCHAR(100) PRIMARY KEY (visitor_id_approx ou user_id anonymisé)
#    - department_id : INT FOREIGN KEY REFERENCES departments(id) ON DELETE SET NULL
#    - created_at : TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#
# 4. TABLE: usage_events
#    Représente les événements d'usage individuels (schéma canonique).
#    - event_id : VARCHAR(64) PRIMARY KEY (hash SHA-256 généré)
#    - event_timestamp : TIMESTAMP NOT NULL
#    - user_id : VARCHAR(100) NOT NULL FOREIGN KEY REFERENCES users(id)
#    - service_id : INT NOT NULL FOREIGN KEY REFERENCES services(id)
#    - action : VARCHAR(100) NOT NULL (ex: 'visit', 'login', 'click')
#    - source : VARCHAR(100) NOT NULL (ex: 'learning_center_nginx')
#    - INDEX idx_event_timestamp (event_timestamp)
#    - INDEX idx_service_user (service_id, user_id)
#
# 5. TABLE: web_logs (Optionnel - Security Analytics)
#    - event_id : VARCHAR(64) PRIMARY KEY (hash SHA-256 généré)
#    - event_timestamp : TIMESTAMP NOT NULL
#    - source_ip : VARCHAR(45) NOT NULL (supporte IPv4/IPv6)
#    - route : VARCHAR(2048) NOT NULL
#    - status_code : INT NOT NULL
#    - user_agent : VARCHAR(1024)
#    - service_id : INT NOT NULL FOREIGN KEY REFERENCES services(id)
#    - INDEX idx_web_logs_timestamp (event_timestamp)
#    - INDEX idx_web_logs_route (route)
#
# 6. TABLE: daily_kpis
#    Représente les indicateurs agrégés par jour et par service.
#    - date : DATE NOT NULL
#    - service_id : INT NOT NULL FOREIGN KEY REFERENCES services(id)
#    - dau_approx : INT NOT NULL DEFAULT 0
#    - wau_approx : INT NOT NULL DEFAULT 0
#    - mau_approx : INT NOT NULL DEFAULT 0
#    - total_requests : INT NOT NULL DEFAULT 0
#    - human_requests : INT NOT NULL DEFAULT 0
#    - page_views : INT NOT NULL DEFAULT 0
#    - api_requests : INT NOT NULL DEFAULT 0
#    - errors_4xx : INT NOT NULL DEFAULT 0
#    - errors_5xx : INT NOT NULL DEFAULT 0
#    - status : VARCHAR(20) NOT NULL DEFAULT 'provisional' CHECK (status IN ('provisional', 'final'))
#    - PRIMARY KEY (date, service_id)
#
# 7. TABLE: ingestion_runs
#    Historique des exécutions du pipeline d'ingestion.
#    - run_id : INT AUTO_INCREMENT PRIMARY KEY
#    - service_id : INT NOT NULL FOREIGN KEY REFERENCES services(id)
#    - start_time : TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#    - end_time : TIMESTAMP
#    - status : VARCHAR(20) NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'RUNNING'))
#    - rows_read : INT DEFAULT 0
#    - rows_rejected : INT DEFAULT 0
#    - duplicates_ignored : INT DEFAULT 0
#    - rows_added : INT DEFAULT 0
#
# 8. TABLE: ingestion_checkpoints
#    Conserve le dernier état d'ingestion valide par service.
#    - service_id : INT PRIMARY KEY FOREIGN KEY REFERENCES services(id)
#    - last_processed_timestamp : TIMESTAMP NULL
#    - last_success_timestamp : TIMESTAMP NULL
#    - last_run_status : VARCHAR(20) CHECK (last_run_status IN ('SUCCESS', 'FAILED'))
# ───────────────────────────────────────────────────────────────────────────────


class StorageRepository(ABC):
    """Interface abstraite définissant les opérations d'accès aux données.

    Conçue pour être implémentée au départ par un FileRepository (CSV/Parquet)
    puis remplacée par une implémentation SQL sans impact sur le reste de l'application.
    """

    @abstractmethod
    def append_events(self, service_name: str, events_df: pd.DataFrame) -> None:
        """Ajoute de nouveaux événements d'usage dans le stockage persistant.

        Si la table/le fichier n'existe pas, il doit être créé.
        Cette opération doit garantir l'idempotence si le pipeline a déjà dédupliqué.
        """

    @abstractmethod
    def append_web_logs(self, service_name: str, logs_df: pd.DataFrame) -> None:
        """Ajoute de nouveaux logs web bruts (pour la sécurité) dans le stockage."""

    @abstractmethod
    def upsert_daily_kpis(self, service_name: str, kpis_df: pd.DataFrame) -> None:
        """Insère ou met à jour les indicateurs quotidiens d'un service.

        Si une date existe déjà, elle doit être écrasée/mise à jour.
        Utile pour gérer la mise à jour incrémentale de la journée provisoire.
        """

    @abstractmethod
    def get_events(self, service_name: str) -> pd.DataFrame:
        """Retourne le DataFrame complet des événements d'usage pour un service."""

    @abstractmethod
    def get_web_logs(self, service_name: str) -> pd.DataFrame:
        """Retourne le DataFrame complet des logs web pour un service."""

    @abstractmethod
    def get_daily_kpis(self, service_name: str) -> pd.DataFrame:
        """Retourne le DataFrame complet des KPIs quotidiens pour un service."""

    @abstractmethod
    def event_exists(self, service_name: str, event_id: str, kind: str = "usage") -> bool:
        """Vérifie si un ID d'événement est déjà présent dans le stockage.

        Args:
            service_name: Nom du service.
            event_id: Identifiant SHA-256 de l'événement.
            kind: 'usage' pour les événements d'usage, 'web_logs' pour les logs web.
        """

    @abstractmethod
    def get_existing_event_ids(self, service_name: str, kind: str = "usage") -> set[str]:
        """Retourne l'ensemble de tous les identifiants d'événements déjà persistés.

        Cette méthode optimise la déduplication en mémoire pour les gros volumes.
        """

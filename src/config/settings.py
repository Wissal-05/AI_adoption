"""Configuration centralisée de la plateforme.

Les valeurs sont chargées dans cet ordre de priorité (du plus fort au moins fort) :
  1. Variables d'environnement système
  2. Fichier `.env` à la racine du projet
  3. Valeurs par défaut définies ici

Aucun chemin absolu n'est codé en dur. Tous les chemins sont relatifs à PROJECT_ROOT
ou résolus depuis la variable d'environnement correspondante.

Variables d'environnement disponibles :
  LEARNING_CENTER_DATA_DIR  — chemin absolu ou relatif vers le dossier Learning Center
  LC_EVENT_SAMPLE_ROWS      — nombre de lignes nginx-events.csv pour l'adoption (défaut: 200000)
  LC_SECURITY_SCAN_MAX_ROWS — nombre de lignes nginx-events.csv pour la sécurité (défaut: 300000)
  ASSISTANT_ENGINE          — moteur IA actif : "keyword" (défaut) ou "llm"
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Puisque le fichier est maintenant dans src/config/settings.py, le parent de src
# est parents[2] (settings.py -> config/ -> src/ -> root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Paramètres globaux de l'application, chargés depuis .env et variables d'env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Chemins de données ─────────────────────────────────────────────────────

    learning_center_data_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "um6p" / "learning_center",
        description=(
            "Dossier contenant les CSV Learning Center. "
            "Peut être un chemin absolu ou relatif au répertoire courant. "
            "Surcharger avec la variable LEARNING_CENTER_DATA_DIR."
        ),
    )

    # ── Noms de fichiers source ────────────────────────────────────────────────

    learning_center_daily_kpis_file: str = "daily-kpis.csv"
    learning_center_nginx_events_file: str = "nginx-events.csv"
    learning_center_top_routes_file: str = "top-routes.csv"

    # ── Paramètres de chargement ───────────────────────────────────────────────

    lc_event_sample_rows: int = Field(
        default=200_000,
        description="Nombre de lignes nginx-events.csv utilisées pour l'échantillon d'adoption.",
        ge=1,
    )

    lc_security_scan_max_rows: int = Field(
        default=300_000,
        description="Nombre de lignes nginx-events.csv scannées pour la détection sécurité.",
        ge=1,
    )

    # ── Métriques ─────────────────────────────────────────────────────────────

    default_inactivity_days: int = Field(
        default=30,
        description="Nombre de jours sans activité pour considérer un utilisateur comme inactif.",
        ge=1,
    )

    underused_service_quantile: float = Field(
        default=0.25,
        description="Quantile en-dessous duquel un service est considéré sous-utilisé.",
        gt=0.0,
        lt=1.0,
    )

    # ── Sécurité ──────────────────────────────────────────────────────────────

    suspicious_route_patterns: list[str] = Field(
        default=[
            "/wp-admin",
            "/wp-login",
            "/.env",
            "/phpmyadmin",
            "/admin",
            "/config",
            "/vendor/phpunit",
        ],
        description="Liste de patterns de routes considérées suspectes.",
    )


    # ── Moteur Groq ───────────────────────────────────────────────────────────

    groq_api_key: str | None = Field(
        default=None,
        description="Clé d'API Groq pour le local tool calling.",
    )

    groq_model: str = Field(
        default="qwen/qwen3.6-27b",
        description="Modèle Groq supportant le tool calling par défaut.",
    )

    # ── Assistant IA ──────────────────────────────────────────────────────────

    assistant_engine: str = Field(
        default="keyword",
        description=(
            "Moteur de l'assistant IA. "
            "'keyword' = moteur par mots-clés intégré. "
            "'llm' = moteur LangChain/LLM (nécessite OPENAI_API_KEY ou équivalent)."
        ),
    )

    # 🗄️ Base de données 🗄️

    db_host: str = Field(
        default="localhost",
        description="Hôte de la base de données PostgreSQL.",
    )
    
    db_port: int = Field(
        default=5432,
        description="Port de la base de données.",
    )
    
    db_name: str = Field(
        default="adoption_analytics",
        description="Nom de la base de données.",
    )
    
    db_user: str = Field(
        default="postgres",
        description="Utilisateur de la base de données.",
    )
    
    db_password: str = Field(
        default="",
        description="Mot de passe de la base de données.",
    )

    # 🗂️ Chemins dérivés (propriétés calculées) 🗂️─────────────────────────────────

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def um6p_data_dir(self) -> Path:
        return self.data_dir / "um6p"

    @property
    def learning_center_repo_dir(self) -> Path:
        """Dossier Learning Center dans le dépôt (fallback si external absent)."""
        return self.um6p_data_dir / "learning_center"

    @property
    def booking_repo_dir(self) -> Path:
        return self.um6p_data_dir / "booking"

    @field_validator("learning_center_data_dir", mode="before")
    @classmethod
    def resolve_lc_dir(cls, v: str | Path) -> Path:
        """Résout le chemin Learning Center (absolu ou relatif à PROJECT_ROOT)."""
        p = Path(v)
        if p.is_absolute():
            return p
        return PROJECT_ROOT / p


# Instance singleton — toute la codebase importe `settings` directement.
settings = Settings()

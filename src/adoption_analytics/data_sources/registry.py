"""Registre de sources de données — Pattern plug-in avec registration déclarative.

## Usage : ajouter une nouvelle source

1. Créer un connecteur dans `data_sources/<nom_service>/connector.py`
2. Créer des loaders dans `data_sources/<nom_service>/loaders.py`
3. Enregistrer le connecteur avec le décorateur `@SourceRegistry.register("nom")`.
4. Déclarer le chargement des données spécifiques dans un plugin d'initialisation.

Les métriques, reporting et l'assistant deviennent immédiatement disponibles
sans aucune modification du code central.

## Contrat de données

- `DashboardData.usage_events` : DataFrame unifié de TOUTES les sources,
  conforme au schéma UsageEvent.
- `DashboardData.web_logs` : DataFrame unifié de TOUS les logs web,
  conforme au schéma WebLog.
- `DashboardData.raw_by_source` : dict[str, dict] indexé par nom de source,
  contenant les DataFrames source-spécifiques (ex: daily-kpis, top-routes).
  Ce dict est extensible sans modifier DashboardData.
- `DashboardData.available_sources` : liste des noms de sources chargées.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

from config.settings import settings
from adoption_analytics.data_sources.base import DataSource, DataSourceConfig
from adoption_analytics.schemas.usage_event import USAGE_COLUMNS, empty_usage_df
from adoption_analytics.schemas.web_log import WEB_LOG_COLUMNS, empty_web_log_df
from adoption_analytics.utils.sample_data import build_sample_usage_events, build_sample_web_logs


# ── Contrat de données central ─────────────────────────────────────────────────

@dataclass(frozen=True)
class DashboardData:
    """Données agrégées du tableau de bord, indépendantes des sources.

    Ce dataclass est conçu pour rester stable même quand de nouvelles sources
    sont ajoutées : les données source-spécifiques sont dans raw_by_source.
    """

    usage_events: pd.DataFrame
    """DataFrame unifié de tous les événements d'usage (schéma UsageEvent)."""

    web_logs: pd.DataFrame
    """DataFrame unifié de tous les logs web bruts (schéma WebLog)."""

    raw_by_source: dict[str, dict[str, pd.DataFrame]]
    """Données brutes enrichies par source, indexées par nom de source.

    Structure : { "learning_center": { "daily_kpis": df, "top_routes": df }, ... }
    Permet à l'UI d'accéder aux données source-spécifiques sans modifier ce dataclass.
    """

    available_sources: list[str]
    """Noms des sources effectivement chargées et non vides."""

    # ── Propriétés de commodité (backward compat) ──────────────────────────────

    @property
    def learning_center_daily(self) -> pd.DataFrame:
        """KPIs quotidiens Learning Center (backward compat)."""
        return self.raw_by_source.get("learning_center", {}).get("daily_kpis", pd.DataFrame())

    @property
    def learning_center_top_routes(self) -> pd.DataFrame:
        """Top routes Learning Center (backward compat)."""
        return self.raw_by_source.get("learning_center", {}).get("top_routes", pd.DataFrame())

    @property
    def learning_center_security_events(self) -> pd.DataFrame:
        """Événements sécurité Learning Center (backward compat).

        Note: depuis la refactorisation, les security events sont produits par
        SecurityService et non plus stockés ici. Cette propriété retourne un
        DataFrame vide pour les anciens consommateurs.
        """
        return self.raw_by_source.get("learning_center", {}).get("security_events", pd.DataFrame())

    @property
    def learning_center_source_dir(self) -> str:
        """Chemin du dossier Learning Center actif (backward compat)."""
        return self.raw_by_source.get("learning_center", {}).get("source_dir", "")

    @property
    def booking_available(self) -> bool:
        """Indique si des données Booking sont disponibles (backward compat)."""
        return "booking" in self.available_sources


# ── Registre plug-in ──────────────────────────────────────────────────────────

# Type des factories de connecteurs : prennent un DataSourceConfig, retournent un DataSource
_ConnectorFactory = Callable[[DataSourceConfig], DataSource]

# Stockage des connecteurs enregistrés : { "nom": (factory_class, config) }
_REGISTRY: dict[str, tuple[type[DataSource], DataSourceConfig]] = {}


def register_source(name: str, config: DataSourceConfig) -> Callable[[type[DataSource]], type[DataSource]]:
    """Décorateur pour enregistrer un connecteur dans le registre global.

    Usage :
        @register_source("booking", DataSourceConfig("booking", path, "usage"))
        class BookingSource(DataSource):
            ...
    """
    def decorator(cls: type[DataSource]) -> type[DataSource]:
        _REGISTRY[name] = (cls, config)
        return cls
    return decorator


def get_registered_sources() -> dict[str, tuple[type[DataSource], DataSourceConfig]]:
    """Retourne une copie du registre courant."""
    return dict(_REGISTRY)


# ── Orchestrateur ─────────────────────────────────────────────────────────────

def load_dashboard_data() -> DashboardData:
    """Charge toutes les sources enregistrées et retourne le DashboardData unifié.

    Séquence :
      1. Charge les données Learning Center (usage + web logs bruts + données spécifiques).
      2. Charge Booking (usage uniquement pour l'instant).
      3. Charge toute autre source déclarée dans le registre.
      4. Concatène les DataFrames conformes au schéma canonique.
      5. Génère des données de démo si aucune source réelle n'est disponible.
    """
    from adoption_analytics.storage.file_repository import FileStorageRepository
    from adoption_analytics.data_sources.learning_center.loaders import (
        load_learning_center_top_routes,
        resolve_learning_center_dir,
    )
    from adoption_analytics.data_sources.booking import BookingSource

    usage_frames: list[pd.DataFrame] = []
    web_log_frames: list[pd.DataFrame] = []
    raw_by_source: dict[str, dict[str, pd.DataFrame]] = {}
    available_sources: list[str] = []

    # ── Learning Center (chargement via le stockage de persistance intermédiaire) ──
    repository = FileStorageRepository()
    lc_usage = repository.get_events("learning_center")
    lc_web_logs = repository.get_web_logs("learning_center")
    lc_daily_kpis = repository.get_daily_kpis("learning_center")
    lc_top_routes = load_learning_center_top_routes()

    raw_by_source["learning_center"] = {
        "daily_kpis": lc_daily_kpis,
        "top_routes": lc_top_routes,
        "source_dir": str(resolve_learning_center_dir()),
    }

    if not lc_usage.empty:
        usage_frames.append(lc_usage)
        available_sources.append("learning_center")
    if not lc_web_logs.empty:
        web_log_frames.append(lc_web_logs)

    # ── Booking ────────────────────────────────────────────────────────────────
    booking_config = DataSourceConfig(
        "booking",
        settings.booking_repo_dir / "usage-events-60d.csv",
        "usage",
    )
    booking_df = BookingSource(booking_config).load()

    booking_daily_kpis_path = settings.booking_repo_dir / "daily-kpis-60d.csv"
    booking_daily_kpis = (
        pd.read_csv(booking_daily_kpis_path)
        if booking_daily_kpis_path.exists()
        else pd.DataFrame()
    )

    if not booking_daily_kpis.empty:
        booking_daily_kpis["date"] = pd.to_datetime(
            booking_daily_kpis["date"],
            errors="coerce",
        )

    raw_by_source["booking"] = {
        "daily_kpis": booking_daily_kpis,
    }

    if not booking_df.empty:
        usage_frames.append(booking_df)
        available_sources.append("booking")

    # ── Sources additionnelles enregistrées dynamiquement ─────────────────────
    for source_name, (cls, config) in _REGISTRY.items():
        if source_name in ("learning_center", "booking"):
            continue  # Déjà chargées ci-dessus
        source_df = cls(config).load()
        if not source_df.empty:
            if config.kind == "usage":
                usage_frames.append(source_df)
            elif config.kind == "web_logs":
                web_log_frames.append(source_df)
            available_sources.append(source_name)
        raw_by_source[source_name] = {}

    # ── Agrégation ────────────────────────────────────────────────────────────
    usage_df = (
        pd.concat(usage_frames, ignore_index=True)
        if usage_frames
        else empty_usage_df()
    )
    web_logs_df = (
        pd.concat(web_log_frames, ignore_index=True)
        if web_log_frames
        else empty_web_log_df()
    )

    # Données de démo si aucune source réelle
    if usage_df.empty:
        usage_df = build_sample_usage_events()
    if web_logs_df.empty:
        web_logs_df = build_sample_web_logs()

    return DashboardData(
        usage_events=usage_df,
        web_logs=web_logs_df,
        raw_by_source=raw_by_source,
        available_sources=available_sources,
    )

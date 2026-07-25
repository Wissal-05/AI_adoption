"""Connecteur Learning Center — classe DataSource.

Responsabilité unique : lire le CSV d'usage Learning Center et normaliser
vers le schéma UsageEvent canonique. Aucune logique métier ici.
"""

import pandas as pd

from adoption_analytics.data_sources.base import DataSource, normalize_usage_events, read_csv_if_exists


class LearningCenterSource(DataSource):
    """Connecteur CSV pour les données d'usage Learning Center.

    Lit le fichier pointé par config.path, normalise vers le schéma
    UsageEvent et retourne un DataFrame propre.
    """

    def load(self) -> pd.DataFrame:
        raw = read_csv_if_exists(self.config.path)
        return normalize_usage_events(raw, source=self.config.name, service="Learning Center")

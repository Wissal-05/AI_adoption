"""Alias de compatibilité ascendante — module learning_center.py.

Ce fichier était le connecteur Learning Center monolithique.
Il a été restructuré en sous-package data_sources/learning_center/.

Ce module réexporte les symboles publics pour ne pas casser les imports existants.
Il sera supprimé une fois tous les imports mis à jour vers le sous-package.

ATTENTION : Ne pas ajouter de nouvelle logique ici.
"""

# Réexportations de compatibilité
from adoption_analytics.data_sources.learning_center.connector import LearningCenterSource  # noqa: F401
from adoption_analytics.data_sources.learning_center.loaders import (  # noqa: F401
    load_learning_center_daily_kpis,
    load_learning_center_security_events,
    load_learning_center_top_routes,
    load_learning_center_usage_sample,
    load_learning_center_web_logs,
    resolve_learning_center_dir,
)

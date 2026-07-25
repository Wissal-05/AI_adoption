"""Connecteur Learning Center — package de source de données.

Ce package expose uniquement des fonctions de chargement et de normalisation
de données. Il ne contient aucune logique métier (métriques, sécurité, reporting).
"""

from adoption_analytics.data_sources.learning_center.connector import LearningCenterSource
from adoption_analytics.data_sources.learning_center.loaders import (
    load_learning_center_daily_kpis,
    load_learning_center_security_events,
    load_learning_center_top_routes,
    load_learning_center_usage_sample,
    resolve_learning_center_dir,
)

__all__ = [
    "LearningCenterSource",
    "load_learning_center_daily_kpis",
    "load_learning_center_security_events",
    "load_learning_center_top_routes",
    "load_learning_center_usage_sample",
    "resolve_learning_center_dir",
]

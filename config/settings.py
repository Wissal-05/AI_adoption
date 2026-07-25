"""Redirection de compatibilité — config/settings.py à la racine.

Ce fichier redirige vers le nouveau fichier de configuration situé dans src/config/settings.py.
Les modules doivent de préférence importer directement depuis le package.
"""

from src.config.settings import settings, Settings, PROJECT_ROOT

"""Package de stockage de la plateforme d'adoption.

Définit le contrat d'interface pour le stockage et l'implémentation POC
basée sur des fichiers CSV structurés.
"""

from adoption_analytics.storage.base import StorageRepository
from adoption_analytics.storage.file_repository import FileStorageRepository

__all__ = ["StorageRepository", "FileStorageRepository"]

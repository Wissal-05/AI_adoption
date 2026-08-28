import re
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from adoption_analytics.auth.repository import PlatformUserRepository
from adoption_analytics.auth.service import AuthService


@dataclass
class ManagedUser:
    """Modèle léger de l'utilisateur géré (ne contient aucun secret)."""
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    is_admin: bool
    created_at: datetime


class UserManagementService:
    """Service métier pour la gestion des utilisateurs."""

    def __init__(self, repository: Optional[PlatformUserRepository] = None, auth_service: Optional[AuthService] = None):
        self._repository = repository or PlatformUserRepository()
        self._auth_service = auth_service or AuthService(repository=self._repository)

    @staticmethod
    def validate_email(email: str) -> str:
        """Valide et normalise un email professionnel UM6P."""
        email = email.strip().lower()
        local_part, separator, domain = email.rpartition('@')
        if separator != '@' or not local_part or domain != 'um6p.ma':
            raise ValueError("L'email doit être une adresse professionnelle valide du domaine @um6p.ma.")
        return email

    @staticmethod
    def validate_role(role: str) -> str:
        """Valide que le rôle est autorisé."""
        role = role.strip()
        if role not in {"IT", "Manager"}:
            raise ValueError("Le rôle doit être exactement 'IT' ou 'Manager'.")
        return role

    @staticmethod
    def validate_password(password: str) -> None:
        """Vérifie la robustesse du mot de passe."""
        if len(password) < 12:
            raise ValueError("Le mot de passe doit contenir au moins 12 caractères.")
        if not re.search(r'[A-Z]', password):
            raise ValueError("Le mot de passe doit contenir au moins une lettre majuscule.")
        if not re.search(r'[a-z]', password):
            raise ValueError("Le mot de passe doit contenir au moins une lettre minuscule.")
        if not re.search(r'\d', password):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre.")
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValueError("Le mot de passe doit contenir au moins un caractère spécial.")

    @staticmethod
    def validate_name(name: str) -> str:
        """Valide et normalise le nom."""
        name = name.strip()
        if not name:
            raise ValueError("Le nom ne peut pas être vide.")
        return name

    def create_user(self, email: str, name: str, password: str, role: str) -> ManagedUser:
        """Crée un nouvel utilisateur avec toutes les validations."""
        valid_email = self.validate_email(email)
        valid_name = self.validate_name(name)
        valid_role = self.validate_role(role)
        self.validate_password(password)

        if self._repository.get_by_email(valid_email):
            raise ValueError("Cet utilisateur existe déjà.")

        password_hash = self._auth_service.hash_password(password)

        user = self._repository.create_user(
            email=valid_email,
            name=valid_name,
            password_hash=password_hash,
            role=valid_role,
            is_active=True,
            is_admin=True
        )

        return ManagedUser(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at
        )

    def list_users(self) -> List[ManagedUser]:
        """Retourne la liste de tous les utilisateurs sans exposer les secrets."""
        users = self._repository.list_users()
        return [
            ManagedUser(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role,
                is_active=u.is_active,
                is_admin=u.is_admin,
                created_at=u.created_at
            ) for u in users
        ]

    def activate_user(self, user_id: int) -> None:
        """Réactive un utilisateur."""
        self._repository.set_active(user_id, True)

    def deactivate_user(self, user_id: int, current_user_id: int) -> None:
        """Désactive un utilisateur, en bloquant l'auto-désactivation."""
        if user_id == current_user_id:
            raise ValueError("Vous ne pouvez pas désactiver votre propre compte.")
        self._repository.set_active(user_id, False)

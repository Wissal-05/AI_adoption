import bcrypt
from dataclasses import dataclass
from typing import Optional

from adoption_analytics.auth.repository import PlatformUserRepository, PlatformUser


@dataclass
class AuthenticatedUser:
    """Modèle léger de l'utilisateur authentifié (ne contient aucun secret)."""
    id: int
    email: str
    name: str
    role: str
    is_admin: bool


class AuthService:
    """Service d'authentification gérant la validation et le hachage des mots de passe."""

    def __init__(self, repository: Optional[PlatformUserRepository] = None):
        self._repository = repository or PlatformUserRepository()

    def hash_password(self, password: str) -> str:
        """Hache un mot de passe avec bcrypt et retourne le hash en string UTF-8."""
        if not password:
            raise ValueError("Le mot de passe ne peut pas être vide.")
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Vérifie un mot de passe contre son hash bcrypt."""
        if not password or not password_hash:
            return False
        
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), 
                password_hash.encode("utf-8")
            )
        except Exception:
            # En cas de hash corrompu ou d'erreur inattendue bcrypt, on retourne False
            return False

    def authenticate(self, email: str, password: str) -> AuthenticatedUser:
        """Authentifie un utilisateur.
        
        Lève ValueError avec un message générique si les credentials sont invalides,
        ou avec un message spécifique si le compte est désactivé.
        """
        if not email or not password:
            raise ValueError("Email ou mot de passe incorrect.")
            
        normalized_email = email.strip().lower()
        
        user = self._repository.get_by_email(normalized_email)
        
        if not user:
            # CAS A: email inexistant -> message générique
            raise ValueError("Email ou mot de passe incorrect.")
            
        if not self.verify_password(password, user.password_hash):
            # CAS B: mot de passe incorrect -> même message générique
            raise ValueError("Email ou mot de passe incorrect.")
            
        if not user.is_active:
            # CAS C: compte désactivé -> message spécifique
            raise ValueError("Ce compte est désactivé. Contactez un administrateur.")
            
        # CAS D: succès
        return AuthenticatedUser(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_admin=user.is_admin
        )

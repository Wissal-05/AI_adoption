import sys
import getpass
import re
from pathlib import Path

# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from adoption_analytics.auth.repository import PlatformUserRepository
from adoption_analytics.auth.service import AuthService

def validate_email(email: str) -> str:
    email = email.strip().lower()
    local_part, separator, domain = email.rpartition('@')
    if separator != '@' or not local_part or domain != 'um6p.ma':
        raise ValueError("L'email doit être une adresse professionnelle valide du domaine @um6p.ma.")
    return email

def validate_role(role: str) -> str:
    role = role.strip()
    if role not in {"IT", "Manager"}:
        raise ValueError("Le rôle doit être exactement 'IT' ou 'Manager'.")
    return role

def validate_password(password: str) -> None:
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

def validate_password_match(password: str, confirm_password: str) -> None:
    if password != confirm_password:
        raise ValueError("Les mots de passe ne correspondent pas.")

def check_bootstrap_allowed(repo) -> None:
    users = repo.list_users()
    if users:
        raise ValueError("Un administrateur initial existe déjà.")

def main():
    try:
        repo = PlatformUserRepository()
        auth = AuthService(repository=repo)

        # 1. Vérification bootstrap (uniquement le premier utilisateur)
        try:
            check_bootstrap_allowed(repo)
        except ValueError as ve:
            print(f"\n{ve}\nUtilisez la gestion des utilisateurs dans Adoption Analytics.")
            sys.exit(1)
        except Exception:
            print("\nErreur de connexion à la base de données. Vérifiez PostgreSQL.")
            sys.exit(1)

        print("\n--- Initialisation du premier Administrateur ---")

        raw_email = input("Email professionnel : ")
        email = validate_email(raw_email)

        name = input("Nom complet : ").strip()
        if not name:
            raise ValueError("Le nom ne peut pas être vide.")

        raw_role = input("Rôle [IT/Manager] : ")
        role = validate_role(raw_role)

        password = getpass.getpass("Mot de passe : ")
        confirm_password = getpass.getpass("Confirmer le mot de passe : ")

        validate_password_match(password, confirm_password)

        validate_password(password)

        # 2. Hachage et création sécurisée
        password_hash = auth.hash_password(password)

        repo.create_user(
            email=email,
            name=name,
            password_hash=password_hash,
            role=role,
            is_active=True,
            is_admin=True
        )

        print(f"\nCompte administrateur initialisé avec succès pour {email} ({role}).")

    except ValueError as ve:
        print(f"\nErreur de validation : {ve}")
        sys.exit(1)
    except Exception:
        print("\nUne erreur technique est survenue.")
        sys.exit(1)

if __name__ == "__main__":
    main()

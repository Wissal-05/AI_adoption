import sys
import getpass
from pathlib import Path

# Ajouter src au PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from adoption_analytics.auth.repository import PlatformUserRepository
from adoption_analytics.auth.service import AuthService
from adoption_analytics.auth.user_management import UserManagementService

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
        email = UserManagementService.validate_email(raw_email)

        raw_name = input("Nom complet : ")
        name = UserManagementService.validate_name(raw_name)

        raw_role = input("Rôle [IT/Manager] : ")
        role = UserManagementService.validate_role(raw_role)

        password = getpass.getpass("Mot de passe : ")
        confirm_password = getpass.getpass("Confirmer le mot de passe : ")

        validate_password_match(password, confirm_password)

        UserManagementService.validate_password(password)

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

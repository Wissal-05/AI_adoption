import pytest
import sys
from pathlib import Path

# Add scripts to path to import validate functions
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from adoption_analytics.auth.user_management import UserManagementService
from create_admin import validate_password_match, check_bootstrap_allowed

validate_email = UserManagementService.validate_email
validate_role = UserManagementService.validate_role
validate_password = UserManagementService.validate_password

def test_validate_email():
    # Valid UM6P emails
    assert validate_email("prenom.nom@um6p.ma") == "prenom.nom@um6p.ma"
    assert validate_email(" ADMIN.TEST@UM6P.MA ") == "admin.test@um6p.ma"

    # Invalid domains
    with pytest.raises(ValueError, match="L'email doit être une adresse professionnelle"):
        validate_email("test@gmail.com")

    with pytest.raises(ValueError, match="L'email doit être une adresse professionnelle"):
        validate_email("test@um6p.ma.com")

def test_validate_role():
    assert validate_role(" IT ") == "IT"
    assert validate_role("Manager") == "Manager"

    with pytest.raises(ValueError, match="Le rôle doit être exactement"):
        validate_role("Admin")

def test_validate_password():
    # Valid password: >= 12 chars, upper, lower, digit, special
    validate_password("MySuper!Password123")

    # Too short
    with pytest.raises(ValueError, match="au moins 12 caractères"):
        validate_password("A1!a")

    # No uppercase
    with pytest.raises(ValueError, match="au moins une lettre majuscule"):
        validate_password("mysuper!password123")

    # No lowercase
    with pytest.raises(ValueError, match="au moins une lettre minuscule"):
        validate_password("MYSUPER!PASSWORD123")

    # No digit
    with pytest.raises(ValueError, match="au moins un chiffre"):
        validate_password("MySuper!Password")

    # No special char
    with pytest.raises(ValueError, match="au moins un caractère spécial"):
        validate_password("MySuperPassword123")

def test_validate_email_strict():
    # Empty local part
    with pytest.raises(ValueError, match="L'email doit être une adresse professionnelle"):
        validate_email("@um6p.ma")

    # Subdomain refused
    with pytest.raises(ValueError, match="L'email doit être une adresse professionnelle"):
        validate_email("user@sub.um6p.ma")

    # Fake domain
    with pytest.raises(ValueError, match="L'email doit être une adresse professionnelle"):
        validate_email("user@um6p.ma.fake")

    # Normalize uppercase
    assert validate_email("USER@UM6P.MA") == "user@um6p.ma"

def test_validate_password_match():
    validate_password_match("Password123!", "Password123!")
    with pytest.raises(ValueError, match="Les mots de passe ne correspondent pas"):
        validate_password_match("Password123!", "password123!")

def test_check_bootstrap_allowed():
    class FakeRepoEmpty:
        def list_users(self):
            return []

    class FakeRepoFull:
        def list_users(self):
            return [{"id": 1, "email": "test@um6p.ma"}]

    # Should pass without error
    check_bootstrap_allowed(FakeRepoEmpty())

    # Should raise error
    with pytest.raises(ValueError, match="Un administrateur initial existe déjà"):
        check_bootstrap_allowed(FakeRepoFull())

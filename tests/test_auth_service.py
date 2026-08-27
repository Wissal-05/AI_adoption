import pytest
from adoption_analytics.auth.service import AuthService, AuthenticatedUser
from adoption_analytics.auth.repository import PlatformUser
from datetime import datetime

class MockPlatformUserRepository:
    def __init__(self):
        # On stocke les utilisateurs de test
        self.users = {}
        
    def get_by_email(self, email):
        return self.users.get(email)

    def _add_test_user(self, user):
        self.users[user.email] = user

@pytest.fixture
def mock_repo():
    return MockPlatformUserRepository()

@pytest.fixture
def auth_service(mock_repo):
    return AuthService(repository=mock_repo)

def test_hash_password(auth_service):
    # A. hash_password produit un hash différent du mot de passe
    password = "MySecretPassword123!"
    hashed = auth_service.hash_password(password)
    
    assert hashed != password
    assert isinstance(hashed, str)
    assert hashed.startswith("$2") # Format bcrypt
    
    with pytest.raises(ValueError):
        auth_service.hash_password("")

def test_verify_password(auth_service):
    password = "CorrectPassword"
    hashed = auth_service.hash_password(password)
    
    # B. verify_password(correct) == True
    assert auth_service.verify_password(password, hashed) is True
    
    # C. verify_password(incorrect) == False
    assert auth_service.verify_password("WrongPassword", hashed) is False
    
    # Invalid hashes should not throw exceptions
    assert auth_service.verify_password(password, "invalid_hash_format") is False

def test_authenticate_inexistent_email(auth_service):
    # D. authenticate email inexistant -> refus (générique)
    with pytest.raises(ValueError, match="Email ou mot de passe incorrect."):
        auth_service.authenticate("nobody@example.com", "password")

def test_authenticate_wrong_password(auth_service, mock_repo):
    # Setup
    password = "RightPassword"
    hashed = auth_service.hash_password(password)
    user = PlatformUser(1, "test@example.com", "Test", hashed, "IT", True, True, datetime.now(), datetime.now())
    mock_repo._add_test_user(user)
    
    # E. authenticate mauvais mot de passe -> refus (générique)
    with pytest.raises(ValueError, match="Email ou mot de passe incorrect."):
        auth_service.authenticate("test@example.com", "WrongPassword")

def test_authenticate_disabled_account(auth_service, mock_repo):
    # Setup
    password = "RightPassword"
    hashed = auth_service.hash_password(password)
    user = PlatformUser(1, "disabled@example.com", "Test", hashed, "IT", False, True, datetime.now(), datetime.now())
    mock_repo._add_test_user(user)
    
    # F. authenticate utilisateur désactivé -> refus (spécifique)
    with pytest.raises(ValueError, match="Ce compte est désactivé."):
        auth_service.authenticate("disabled@example.com", password)

def test_authenticate_success(auth_service, mock_repo):
    # Setup
    password = "RightPassword"
    hashed = auth_service.hash_password(password)
    user = PlatformUser(1, "valid@example.com", "Valid User", hashed, "Manager", True, True, datetime.now(), datetime.now())
    mock_repo._add_test_user(user)
    
    # G. authenticate utilisateur actif + bon password -> AuthenticatedUser
    # Note: the service uses normalization (strip/lower)
    auth_user = auth_service.authenticate(" VALID@example.com ", password)
    
    assert isinstance(auth_user, AuthenticatedUser)
    assert auth_user.id == 1
    assert auth_user.email == "valid@example.com"
    assert auth_user.name == "Valid User"
    assert auth_user.role == "Manager"
    assert auth_user.is_admin is True
    
    # H. AuthenticatedUser ne contient pas password_hash
    assert not hasattr(auth_user, "password_hash")

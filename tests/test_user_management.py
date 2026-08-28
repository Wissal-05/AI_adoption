import pytest
from datetime import datetime

from adoption_analytics.auth.user_management import UserManagementService, ManagedUser
from adoption_analytics.auth.service import AuthService


class FakeUser:
    def __init__(self, id, email, name, password_hash, role, is_active, is_admin):
        self.id = id
        self.email = email
        self.name = name
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active
        self.is_admin = is_admin
        self.created_at = datetime.now()


class FakePlatformUserRepository:
    def __init__(self):
        self.users = {}
        self.next_id = 1

    def get_by_email(self, email: str):
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def create_user(self, email, name, password_hash, role, is_active=True, is_admin=False):
        user = FakeUser(self.next_id, email, name, password_hash, role, is_active, is_admin)
        self.users[self.next_id] = user
        self.next_id += 1
        return user

    def list_users(self):
        return list(self.users.values())

    def set_active(self, user_id, active):
        if user_id in self.users:
            self.users[user_id].is_active = active


@pytest.fixture
def repo():
    return FakePlatformUserRepository()

@pytest.fixture
def auth_service(repo):
    return AuthService(repository=repo)

@pytest.fixture
def service(repo, auth_service):
    return UserManagementService(repository=repo, auth_service=auth_service)


def test_email_validation_valid(service):
    assert service.validate_email("user.test@um6p.ma") == "user.test@um6p.ma"
    assert service.validate_email("  USER@UM6P.MA  ") == "user@um6p.ma"

def test_email_validation_external_refused(service):
    with pytest.raises(ValueError):
        service.validate_email("user@gmail.com")

def test_email_validation_subdomain_refused(service):
    with pytest.raises(ValueError):
        service.validate_email("user@sub.um6p.ma")
    with pytest.raises(ValueError):
        service.validate_email("user@um6p.ma.fake")
    with pytest.raises(ValueError):
        service.validate_email("@um6p.ma")

def test_name_validation_empty_refused(service):
    with pytest.raises(ValueError):
        service.validate_name("   ")
    with pytest.raises(ValueError):
        service.validate_name("")

def test_role_validation_invalid_refused(service):
    with pytest.raises(ValueError):
        service.validate_role("Admin")
    with pytest.raises(ValueError):
        service.validate_role("User")

def test_password_validation_weak_refused(service):
    # Too short
    with pytest.raises(ValueError):
        service.validate_password("Aa1!abcd")
    # No uppercase
    with pytest.raises(ValueError):
        service.validate_password("abcdefg1!aaaa")
    # No lowercase
    with pytest.raises(ValueError):
        service.validate_password("ABCDEFG1!AAAA")
    # No digit
    with pytest.raises(ValueError):
        service.validate_password("Abcdefg!aaaaa")
    # No special
    with pytest.raises(ValueError):
        service.validate_password("Abcdefg1aaaaa")

def test_create_user_valid(service):
    user = service.create_user(
        email="new.user@um6p.ma",
        name="New User",
        password="StrongPassword123!",
        role="IT"
    )
    assert isinstance(user, ManagedUser)
    assert user.email == "new.user@um6p.ma"
    assert user.name == "New User"
    assert user.role == "IT"
    assert user.is_active is True
    assert user.is_admin is True
    assert not hasattr(user, "password_hash")

def test_create_user_existing_refused(service, repo):
    repo.create_user("exist@um6p.ma", "Existing", "hash", "IT")
    with pytest.raises(ValueError):
        service.create_user("exist@um6p.ma", "Exist", "StrongPassword123!", "IT")

def test_list_users_no_password_hash(service, repo):
    repo.create_user("u1@um6p.ma", "U1", "hash1", "IT")
    repo.create_user("u2@um6p.ma", "U2", "hash2", "Manager")
    users = service.list_users()
    assert len(users) == 2
    for user in users:
        assert isinstance(user, ManagedUser)
        assert not hasattr(user, "password_hash")

def test_deactivate_reactivate_user(service, repo):
    u1 = repo.create_user("u1@um6p.ma", "U1", "hash", "IT", is_active=True)
    service.deactivate_user(u1.id, current_user_id=999)
    assert not repo.users[u1.id].is_active

    service.activate_user(u1.id)
    assert repo.users[u1.id].is_active

def test_self_deactivation_refused(service, repo):
    u1 = repo.create_user("u1@um6p.ma", "U1", "hash", "IT", is_active=True)
    with pytest.raises(ValueError):
        service.deactivate_user(u1.id, current_user_id=u1.id)

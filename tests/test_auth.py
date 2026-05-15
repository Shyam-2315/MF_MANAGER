from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import RoleChecker, get_current_user
from app.exceptions import ForbiddenException, UnauthorizedException
from app.main import app
from app.models.user import UserRole
from app.schemas.auth import LoginResponse, RefreshResponse
from app.schemas.user import UserRead
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.services.auth_service import AuthService


def make_user_read(role: UserRole = UserRole.CUSTOMER, is_active: bool = True) -> UserRead:
    now = datetime.now(UTC)
    return UserRead(
        id=uuid4(),
        full_name="Test User",
        email="test@example.com",
        phone="+15555550123",
        role=role,
        is_active=is_active,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


def test_auth_routes_register_login_refresh_and_me(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuthService:
        def __init__(self, _db) -> None:
            pass

        async def register(self, payload):
            user = make_user_read()
            return user.model_copy(update={"email": str(payload.email), "full_name": payload.full_name, "phone": payload.phone})

        async def login(self, email: str, _password: str) -> LoginResponse:
            user = make_user_read()
            return LoginResponse(
                access_token="access-token",
                refresh_token="refresh-token",
                expires_in=1800,
                role=UserRole.CUSTOMER,
                user=user.model_copy(update={"email": email}),
            )

        async def refresh(self, _refresh_token: str) -> RefreshResponse:
            return RefreshResponse(
                access_token="new-access-token",
                refresh_token="new-refresh-token",
                expires_in=1800,
                role=UserRole.CUSTOMER,
            )

    async def fake_current_user():
        return make_user_read()

    monkeypatch.setattr("app.routes.auth.AuthService", FakeAuthService)
    app.dependency_overrides[get_current_user] = fake_current_user

    client = TestClient(app)

    register_response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "new@example.com",
            "phone": "+15555550123",
            "password": "strongpassword",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "new@example.com"

    login_response = client.post("/api/auth/login", json={"email": "new@example.com", "password": "strongpassword"})
    assert login_response.status_code == 200
    assert login_response.json()["access_token"] == "access-token"
    assert login_response.json()["refresh_token"] == "refresh-token"
    assert login_response.json()["role"] == "CUSTOMER"

    token_response = client.post(
        "/api/auth/token",
        data={"username": "advisor@test.com", "password": "StrongPassword123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_response.status_code == 200
    assert token_response.json()["access_token"] == "access-token"
    assert token_response.json()["refresh_token"] == "refresh-token"
    assert token_response.json()["token_type"] == "bearer"

    refresh_response = client.post("/api/auth/refresh", json={"refresh_token": "refresh-token"})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] == "new-access-token"

    me_response = client.get("/api/auth/me", headers={"Authorization": "Bearer access-token"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "test@example.com"


def test_register_rejects_invalid_password() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "new@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_swagger_oauth2_login_rejects_missing_form_fields() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/token",
        data={"username": "advisor@test.com"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


def test_bcrypt_hashing_and_jwt_token_types() -> None:
    password_hash = get_password_hash("strongpassword")

    assert password_hash != "strongpassword"
    assert verify_password("strongpassword", password_hash)
    assert not verify_password("wrongpassword", password_hash)

    user_id = str(uuid4())
    access_token = create_access_token(user_id, claims={"role": UserRole.CUSTOMER.value})
    refresh_token = create_refresh_token(user_id, claims={"role": UserRole.CUSTOMER.value})

    assert decode_access_token(access_token)["sub"] == user_id
    assert decode_refresh_token(refresh_token)["sub"] == user_id

    with pytest.raises(UnauthorizedException):
        decode_access_token(refresh_token)


@pytest.mark.anyio
async def test_auth_service_rejects_inactive_user(monkeypatch: pytest.MonkeyPatch) -> None:
    inactive_user = SimpleNamespace(
        id=uuid4(),
        email="inactive@example.com",
        password_hash=get_password_hash("strongpassword"),
        role=UserRole.CUSTOMER,
        is_active=False,
    )

    class FakeUserRepository:
        def __init__(self, _db) -> None:
            pass

        async def get_by_email(self, _email: str):
            return inactive_user

    monkeypatch.setattr("app.services.auth_service.UserRepository", FakeUserRepository)

    service = AuthService(db=SimpleNamespace())

    with pytest.raises(UnauthorizedException):
        await service.login("inactive@example.com", "strongpassword")


def test_role_checker_rejects_disallowed_role() -> None:
    checker = RoleChecker(UserRole.SUPER_ADMIN)
    user = SimpleNamespace(role=UserRole.CUSTOMER)

    with pytest.raises(ForbiddenException):
        checker(user)

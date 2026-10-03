"""Integration tests for Login and Access Token APIs (AUTH-004)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from argon2 import PasswordHasher, Type
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User, UserCredential
from app.modules.auth.password import PasswordService


@pytest.fixture
async def auth_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with get_session overridden to db_session."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_login_successful_flow_and_me_endpoint(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify valid login returns token, updates last_login_at in DB, and allows GET /api/auth/me."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"user_{unique_suffix}@example.com"
    password = "ValidSecretPassword123!"
    display_name = "Login Test User"

    # Register first
    reg_resp = await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert reg_resp.status_code == 202

    # Check last_login_at is initially None
    stmt = select(User).where(User.email_normalized == email)
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.last_login_at is None

    # Perform login
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email.upper(), "password": password},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == get_settings().auth.access_token_minutes * 60
    token = data["access_token"]

    # Verify last_login_at was updated in PostgreSQL
    await db_session.refresh(user)
    assert user.last_login_at is not None

    # Test GET /api/auth/me with Bearer token
    me_resp = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["id"] == str(user.id)
    assert me_data["email"] == email
    assert me_data["display_name"] == display_name
    assert me_data["status"] == "active"


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify wrong password returns 401 with standard error envelope."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"user_{unique_suffix}@example.com"
    password = "ValidSecretPassword123!"

    # Register
    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Test"},
    )

    # Wrong password
    resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert body["error"]["message"] == "Invalid email or password"

    # Nonexistent email
    resp_unknown = await auth_client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": password},
    )
    assert resp_unknown.status_code == 401
    body_unknown = resp_unknown.json()
    assert body_unknown["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert body_unknown["error"]["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_disabled_account_returns_401(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify disabled account returns identical 401 error."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"disabled_{unique_suffix}@example.com"
    password = "ValidSecretPassword123!"

    # Register
    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Disabled User"},
    )

    # Disable user in DB
    stmt = select(User).where(User.email_normalized == email)
    user = (await db_session.execute(stmt)).scalar_one()
    user.status = UserStatus.DISABLED.value
    await db_session.commit()

    # Attempt login
    resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert body["error"]["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_me_endpoint_requires_auth_and_rejects_tampered_token(
    auth_client: AsyncClient,
) -> None:
    """Verify GET /api/auth/me rejects missing or tampered credentials."""
    # No auth header
    resp_no_auth = await auth_client.get("/api/auth/me")
    assert resp_no_auth.status_code == 401
    assert resp_no_auth.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Malformed bearer token
    resp_bad = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp_bad.status_code == 401
    assert resp_bad.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_login_triggers_password_rehash(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that stored hash with older parameters is transparently upgraded on login."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"rehash_{unique_suffix}@example.com"
    password = "ValidSecretPassword123!"

    # Create user with an intentionally low-cost Argon2id hash (e.g. t=1, m=8192, p=1)
    legacy_hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, type=Type.ID)
    legacy_hash = legacy_hasher.hash(password)

    user = User(
        email_normalized=email,
        display_name="Legacy Hash User",
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(user)
    await db_session.flush()

    credential = UserCredential(
        user_id=user.id,
        password_hash=legacy_hash,
    )
    db_session.add(credential)
    await db_session.commit()

    # Confirm initial hash is legacy
    assert "m=8192,t=1,p=1" in legacy_hash

    # Login
    resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200

    # Verify credential was rehashed in PostgreSQL
    await db_session.refresh(credential)
    assert credential.password_hash != legacy_hash
    # Confirm updated hash validates with current service
    pwd_service = PasswordService()
    assert pwd_service.verify_password(password, credential.password_hash).valid is True
    assert pwd_service.verify_password(password, credential.password_hash).needs_rehash is False

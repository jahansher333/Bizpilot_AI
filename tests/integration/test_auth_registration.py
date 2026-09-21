"""Integration tests for user registration API."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User, UserCredential
from app.modules.auth.password import PasswordService


@pytest.fixture
async def registration_client(
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
async def test_register_new_user_success(
    registration_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify valid registration returns HTTP 202 and creates User and UserCredential."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"newuser_{unique_suffix}@example.com"
    password = "CorrectHorseBatteryStaple123"
    display_name = "New Valid User"

    response = await registration_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": "Registration request accepted. Please proceed to login."
    }

    # Verify User in PostgreSQL
    stmt = select(User).where(User.email_normalized == email)
    result = await db_session.execute(stmt)
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email_normalized == email
    assert user.display_name == display_name
    assert user.status == UserStatus.ACTIVE.value

    # Verify UserCredential in PostgreSQL
    stmt_cred = select(UserCredential).where(UserCredential.user_id == user.id)
    result_cred = await db_session.execute(stmt_cred)
    cred = result_cred.scalar_one_or_none()
    assert cred is not None
    assert cred.password_hash.startswith("$argon2id$")
    assert password not in cred.password_hash

    # Verify password against hash
    pwd_service = PasswordService()
    verify_result = pwd_service.verify_password(password, cred.password_hash)
    assert verify_result.valid is True


@pytest.mark.asyncio
async def test_register_duplicate_email_strict_non_enumeration(
    registration_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify duplicate email returns identical HTTP 202 and does not duplicate/modify records."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"dup_{unique_suffix}@example.com"
    original_password = "OriginalPassword123"

    # First registration
    resp1 = await registration_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": original_password,
            "display_name": "Original User",
        },
    )
    assert resp1.status_code == 202

    # Get original credential hash
    stmt = select(User).where(User.email_normalized == email)
    user1 = (await db_session.execute(stmt)).scalar_one()
    stmt_cred = select(UserCredential).where(UserCredential.user_id == user1.id)
    cred1 = (await db_session.execute(stmt_cred)).scalar_one()
    original_hash = cred1.password_hash

    # Second registration with uppercase/whitespace email variant and different password
    variant_email = f"  {email.upper()}  "
    resp2 = await registration_client.post(
        "/api/auth/register",
        json={
            "email": variant_email,
            "password": "SecondAttemptPassword456",
            "display_name": "Imposter User",
        },
    )
    assert resp2.status_code == 202
    assert resp2.json() == resp1.json()

    # Verify no duplicate user was created
    stmt_all = select(User).where(User.email_normalized == email)
    users = (await db_session.execute(stmt_all)).scalars().all()
    assert len(users) == 1

    # Verify existing credential was not modified or overwritten
    await db_session.refresh(cred1)
    assert cred1.password_hash == original_hash

    # Verify original password still validates
    pwd_service = PasswordService()
    assert pwd_service.verify_password(original_password, cred1.password_hash).valid is True
    assert pwd_service.verify_password("SecondAttemptPassword456", cred1.password_hash).valid is False


@pytest.mark.asyncio
async def test_register_password_policy_rejection_returns_422(
    registration_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify passwords failing domain policy (e.g. denylisted) return 422 Validation error."""
    response = await registration_client.post(
        "/api/auth/register",
        json={
            "email": "denylisted@example.com",
            "password": "password123456",  # in COMMON_PASSWORDS_DENYLIST
            "display_name": "User",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "too common or easily guessed" in data["error"]["message"]

    # Verify user was not persisted
    stmt = select(User).where(User.email_normalized == "denylisted@example.com")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_register_malformed_email_returns_422(
    registration_client: AsyncClient,
) -> None:
    """Verify malformed email payload returns 422 Validation error."""
    response = await registration_client.post(
        "/api/auth/register",
        json={
            "email": "not-a-valid-email",
            "password": "ValidPassword123!",
            "display_name": "User",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_extra_fields_rejected_with_422(
    registration_client: AsyncClient,
) -> None:
    """Verify extra fields like status or role are rejected."""
    response = await registration_client.post(
        "/api/auth/register",
        json={
            "email": "extra@example.com",
            "password": "ValidPassword123!",
            "display_name": "User",
            "status": "admin",
            "role": "owner",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"

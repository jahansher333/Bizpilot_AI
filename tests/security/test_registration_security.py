"""Security tests for user registration flow."""

from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import RegistrationService


@pytest.fixture
async def sec_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_registration_does_not_log_plaintext_password_or_hash(
    sec_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify plaintext passwords and password hashes never appear in application logs."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"sec_{unique_suffix}@example.com"
    secret_password = "SuperSecretUnmaskedPassword123!"

    with caplog.at_level(logging.DEBUG):
        response = await sec_client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": secret_password,
                "display_name": "Security User",
            },
        )
        assert response.status_code == 202

    for record in caplog.records:
        assert secret_password not in record.message
        assert "$argon2id$" not in record.message


@pytest.mark.asyncio
async def test_registration_response_does_not_leak_secrets_or_metadata(
    sec_client: AsyncClient,
) -> None:
    """Verify response payload does not return user_id, status, tokens, or hashes."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"sec_leak_{unique_suffix}@example.com"
    password = "SafePasswordForTesting123!"

    response = await sec_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "No Leak User",
        },
    )
    assert response.status_code == 202
    data = response.json()

    # Exact expected contract only
    assert list(data.keys()) == ["message"]
    assert password not in str(data)
    assert "$argon2id$" not in str(data)

    # Verify no tokens or cookies in headers
    assert "set-cookie" not in response.headers
    assert "authorization" not in response.headers


@pytest.mark.asyncio
async def test_uniform_status_and_body_for_new_and_duplicate(
    sec_client: AsyncClient,
) -> None:
    """Verify new registration and duplicate registration return identical status and body."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"sec_uniform_{unique_suffix}@example.com"
    password = "ConsistentPassword123!"

    resp_new = await sec_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "User",
        },
    )
    resp_dup = await sec_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": "User",
        },
    )

    assert resp_new.status_code == 202
    assert resp_dup.status_code == 202
    assert resp_new.json() == resp_dup.json()


@pytest.mark.asyncio
async def test_credential_creation_failure_rolls_back_user(
    db_session: AsyncSession,
) -> None:
    """Verify atomicity: if credential persistence fails, User is not committed."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"rollback_test_{unique_suffix}@example.com"

    service = RegistrationService(session=db_session)

    # Patch create_credential to raise an exception
    with patch.object(
        service._repository,
        "create_credential",
        AsyncMock(side_effect=RuntimeError("Simulated credential persistence failure")),
    ):
        req = RegisterRequest(
            email=email,
            password="RollbackPassword123!",
            display_name="Rollback User",
        )
        with pytest.raises(RuntimeError, match="Simulated credential persistence failure"):
            await service.register(req)

    # Verify user was rolled back and is not in PostgreSQL
    stmt = select(User).where(User.email_normalized == email)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None

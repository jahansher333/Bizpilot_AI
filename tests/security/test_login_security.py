"""Security and non-enumeration tests for Login and Access Token issuance (AUTH-004)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User
from app.modules.auth.tokens import TokenService


@pytest.fixture
async def sec_client(
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
async def test_non_enumeration_identical_responses_across_failure_modes(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify identical 401 response for: unknown email, wrong password, and disabled account."""
    unique_active = uuid.uuid4().hex[:8]
    active_email = f"active_{unique_active}@example.com"
    correct_password = "CorrectHorseBatteryStaple123"

    # Register active user
    await sec_client.post(
        "/api/auth/register",
        json={"email": active_email, "password": correct_password, "display_name": "Active User"},
    )

    # Register and disable a second user
    unique_disabled = uuid.uuid4().hex[:8]
    disabled_email = f"disabled_{unique_disabled}@example.com"
    await sec_client.post(
        "/api/auth/register",
        json={"email": disabled_email, "password": correct_password, "display_name": "Disabled User"},
    )
    stmt = select(User).where(User.email_normalized == disabled_email)
    user_dis = (await db_session.execute(stmt)).scalar_one()
    user_dis.status = UserStatus.DISABLED.value
    await db_session.commit()

    # 1. Unknown email
    resp_unknown = await sec_client.post(
        "/api/auth/login",
        json={"email": "completely_unknown_user@example.com", "password": correct_password},
    )

    # 2. Existing user, wrong password
    resp_wrong_pwd = await sec_client.post(
        "/api/auth/login",
        json={"email": active_email, "password": "WrongPasswordAttempt123"},
    )

    # 3. Disabled user, correct password
    resp_disabled = await sec_client.post(
        "/api/auth/login",
        json={"email": disabled_email, "password": correct_password},
    )

    # Assert identical HTTP status code and non-enumerating error details
    for resp in (resp_unknown, resp_wrong_pwd, resp_disabled):
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert body["error"]["message"] == "Invalid email or password"
        assert body["error"]["details"] is None
        assert "correlation_id" in body["error"]



@pytest.mark.asyncio
async def test_access_token_claims_confidentiality_and_strict_scoping(
    sec_client: AsyncClient,
) -> None:
    """Verify that issued tokens contain only unprivileged claims and no PII/tenant data."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"claims_{unique_suffix}@example.com"
    password = "CorrectHorseBatteryStaple123"

    await sec_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Claims Test User"},
    )

    login_resp = await sec_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Decode without verification just to inspect all unencrypted payload fields
    unverified_payload = jwt.decode(token, options={"verify_signature": False})

    allowed_claims = {"sub", "exp", "iat", "nbf", "jti", "type", "iss", "aud"}
    actual_claims = set(unverified_payload.keys())

    assert actual_claims == allowed_claims
    assert unverified_payload["type"] == "access"
    assert unverified_payload["iss"] == "bizpilot-api"
    assert unverified_payload["aud"] == "bizpilot-web"

    # Strict exclusion: verify NO sensitive/tenant data is present
    forbidden_keys = {
        "email",
        "display_name",
        "role",
        "roles",
        "organization_id",
        "permissions",
        "password",
        "hash",
    }
    assert not (actual_claims & forbidden_keys)


@pytest.mark.asyncio
async def test_tampered_and_alg_none_token_rejected_at_auth_me(
    sec_client: AsyncClient,
) -> None:
    """Verify signature tampering and alg=none attacks are strictly rejected."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"tamper_{unique_suffix}@example.com"
    password = "CorrectHorseBatteryStaple123"

    await sec_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Tamper Test User"},
    )

    login_resp = await sec_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    valid_token = login_resp.json()["access_token"]

    # Tamper with the signature bytes (flip first character of signature segment)
    header, payload_b64, sig = valid_token.split(".")
    tampered_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    tampered_token = f"{header}.{payload_b64}.{tampered_sig}"
    resp_tampered = await sec_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert resp_tampered.status_code == 401

    assert resp_tampered.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Alg=none forged token
    unverified_payload = jwt.decode(valid_token, options={"verify_signature": False})
    none_token = jwt.encode(unverified_payload, key="", algorithm="none")
    resp_none = await sec_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {none_token}"},
    )
    assert resp_none.status_code == 401
    assert resp_none.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_user_disabled_after_token_issuance_is_immediately_rejected(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that if a user is disabled in DB, their previously issued token cannot access /me."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"revoked_{unique_suffix}@example.com"
    password = "CorrectHorseBatteryStaple123"

    await sec_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Revoked User"},
    )

    login_resp = await sec_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_resp.json()["access_token"]

    # Initially valid
    me_resp1 = await sec_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp1.status_code == 200

    # Administrator disables the user in PostgreSQL
    stmt = select(User).where(User.email_normalized == email)
    user = (await db_session.execute(stmt)).scalar_one()
    user.status = UserStatus.DISABLED.value
    await db_session.commit()

    # Access is now immediately denied
    me_resp2 = await sec_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp2.status_code == 401
    assert me_resp2.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_login_extra_fields_forbidden(
    sec_client: AsyncClient,
) -> None:
    """Verify extra fields in login payload are rejected with 422."""
    resp = await sec_client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "ValidPassword123!",
            "admin": True,
            "role": "superuser",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

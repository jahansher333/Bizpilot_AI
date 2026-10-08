"""Security tests for User Logout, Session Revocation, and Cross-User Isolation (AUTH-006)."""

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
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.refresh import generate_refresh_token, hash_refresh_token
from tests.helpers import refresh_cookie, refresh_cookie_header


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


# 1. Cross-User Isolation: User A cannot log out User B


@pytest.mark.asyncio
async def test_logout_all_cross_user_isolation(
    auth_client: AsyncClient,
) -> None:
    """Verify User A calling /logout-all revokes ONLY User A's sessions, never User B's."""
    user_a_email = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    # Create User A
    await auth_client.post(
        "/api/auth/register",
        json={"email": user_a_email, "password": password, "display_name": "User A"},
    )
    resp_a = await auth_client.post(
        "/api/auth/login",
        json={"email": user_a_email, "password": password},
    )
    jwt_a = resp_a.json()["access_token"]
    r_a = refresh_cookie(resp_a)

    # Create User B
    await auth_client.post(
        "/api/auth/register",
        json={"email": user_b_email, "password": password, "display_name": "User B"},
    )
    resp_b = await auth_client.post(
        "/api/auth/login",
        json={"email": user_b_email, "password": password},
    )
    r_b = refresh_cookie(resp_b)

    # User A calls /logout-all
    logout_all_a = await auth_client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {jwt_a}"},
    )
    assert logout_all_a.status_code == 200

    # User A is denied refresh
    ref_a = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r_a))
    assert ref_a.status_code == 401

    # CRITICAL: User B remains fully active and can refresh successfully
    ref_b = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r_b))
    assert ref_b.status_code == 200
    assert refresh_cookie(ref_b)


# 2. Strict Non-Enumeration on Unknown Token


@pytest.mark.asyncio
async def test_logout_unknown_token_non_enumeration(auth_client: AsyncClient) -> None:
    """Verify unknown logout token returns generic 401 without leaking existence or system state."""
    unknown_token = generate_refresh_token()
    resp = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(unknown_token))

    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["code"] == "AUTHENTICATION_REQUIRED"
    assert err["message"] == "Invalid or expired refresh token"
    assert err["details"] is None
    assert err["correlation_id"] is not None


# 3. Plaintext Confidentiality: No Raw Tokens Persisted or Leaked in Responses


@pytest.mark.asyncio
async def test_logout_response_contains_no_sensitive_metadata(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify logout response never leaks token hashes, family IDs, user IDs, or raw tokens."""
    email = f"leakcheck_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Leak Check"},
    )
    login_resp = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    raw_token = refresh_cookie(login_resp)

    logout_resp = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(raw_token))
    assert logout_resp.status_code == 200
    body = logout_resp.json()

    # Exact expected fields
    assert set(body.keys()) == {"status", "message"}
    assert body["status"] == "success"

    # Verify no raw token plaintext is stored anywhere in the database
    stmt = select(RefreshToken).where(RefreshToken.token_hash == raw_token)
    assert (await db_session.execute(stmt)).first() is None


# 4. Strict Input Bounds and Validation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_cookie",
    [None, "", "   ", "short", "a" * 129, generate_refresh_token()],
)
async def test_logout_input_boundary_defense(
    auth_client: AsyncClient,
    bad_cookie: str | None,
) -> None:
    """A missing, malformed, out-of-bounds or unknown refresh cookie is a uniform 401 (SEC-P1 F3)."""
    headers = refresh_cookie_header(bad_cookie) if bad_cookie is not None else {}
    resp = await auth_client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"] == {
        "code": "AUTHENTICATION_REQUIRED",
        "message": "Invalid or expired refresh token",
        "details": None,
        "correlation_id": resp.json()["error"]["correlation_id"],
    }


@pytest.mark.asyncio
async def test_logout_input_ignores_body_tokens(
    auth_client: AsyncClient,
) -> None:
    """The old JSON-body transport is gone: a token in the body is never read."""
    email = f"body_{uuid.uuid4().hex[:8]}@example.com"
    await auth_client.post("/api/auth/register", json={"email": email, "password": "ValidSecretPassword123!", "display_name": "Body"})
    login = await auth_client.post("/api/auth/login", json={"email": email, "password": "ValidSecretPassword123!"})
    resp = await auth_client.post("/api/auth/logout", json={"refresh_token": refresh_cookie(login)})
    assert resp.status_code == 401


# 5. Disabled User Revocation


@pytest.mark.asyncio
async def test_disabled_user_can_revoke_session_via_logout(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify a disabled account can still revoke its refresh session to cleanly terminate it."""
    email = f"dis_lo_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Dis User"},
    )
    login_resp = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r1 = refresh_cookie(login_resp)

    # Disable the user in DB
    stmt_user = select(User).where(User.email_normalized == email)
    user = (await db_session.execute(stmt_user)).scalar_one()
    user.status = UserStatus.DISABLED.value
    await db_session.commit()

    # Logout is a revocation operation and succeeds
    logout_resp = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(r1))
    assert logout_resp.status_code == 200

    # Refresh remains denied
    ref_resp = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r1))
    assert ref_resp.status_code == 401

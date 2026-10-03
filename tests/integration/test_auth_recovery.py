"""Integration tests for Password Recovery, Reset Token Lifecycle, and Concurrency (AUTH-007)."""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.models import PasswordResetToken, RefreshToken, User
from app.modules.auth.recovery import (
    InMemoryPasswordResetDeliveryAdapter,
    hash_password_reset_token,
    set_delivery_adapter,
)


@pytest.fixture
def test_delivery_adapter() -> InMemoryPasswordResetDeliveryAdapter:
    """Fixture providing an in-memory delivery adapter and resetting it after test."""
    adapter = InMemoryPasswordResetDeliveryAdapter()
    set_delivery_adapter(adapter)
    yield adapter
    adapter.clear()


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
async def test_password_recovery_and_reset_end_to_end_lifecycle(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify full recovery lifecycle:

    Register -> Login -> Forgot Password -> Reset Password ->
    Old Password Fails -> New Password Succeeds -> Old Refresh Token Revoked.
    """
    email = f"recovery_{uuid.uuid4().hex[:8]}@example.com"
    old_password = "InitialPassword123!"
    new_password = "BrandNewSecretPassword2026!"

    # 1. Register & Login
    reg_resp = await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": old_password, "display_name": "Recovery User"},
    )
    assert reg_resp.status_code == 202

    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": old_password},
    )
    assert login_resp.status_code == 200
    old_refresh_token = login_resp.json()["refresh_token"]

    # 2. Forgot Password Request
    forgot_resp = await auth_client.post(
        "/api/auth/forgot-password",
        json={"email": email},
    )
    assert forgot_resp.status_code == 200
    assert forgot_resp.json()["status"] == "success"

    # Capture token delivered via adapter
    assert len(test_delivery_adapter.dispatches) == 1
    dispatch = test_delivery_adapter.dispatches[0]
    assert dispatch["email"] == email.lower()
    raw_reset_token = dispatch["token"]

    # 3. Reset Password with the raw token
    reset_resp = await auth_client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset_token, "new_password": new_password},
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "success"

    # Verify DB: token consumed_at is set
    token_hash = hash_password_reset_token(raw_reset_token)
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    token_row = (await db_session.execute(stmt)).scalar_one()
    assert token_row.consumed_at is not None

    # 4. Old password login must fail
    fail_login = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": old_password},
    )
    assert fail_login.status_code == 401

    # 5. New password login must succeed
    new_login = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]

    # 6. Prior refresh session must be revoked
    old_refresh_fail = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert old_refresh_fail.status_code == 401


@pytest.mark.asyncio
async def test_reset_token_single_use_cannot_be_reused(
    auth_client: AsyncClient,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify a reset token cannot be redeemed more than once."""
    email = f"singleuse_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPassword123!"

    await auth_client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Single Use"})
    await auth_client.post("/api/auth/forgot-password", json={"email": email})
    token = test_delivery_adapter.dispatches[0]["token"]

    # First redemption succeeds
    r1 = await auth_client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewSecretPassword1!"})
    assert r1.status_code == 200

    # Second redemption with same token fails with 401
    r2 = await auth_client.post("/api/auth/reset-password", json={"token": token, "new_password": "AnotherPassword2!"})
    assert r2.status_code == 401
    assert r2.json()["error"]["message"] == "Invalid or expired password reset token"


@pytest.mark.asyncio
async def test_multiple_forgot_password_invalidates_previous_token(
    auth_client: AsyncClient,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Founder Decision 3: New reset request invalidates all previous unconsumed tokens."""
    email = f"multi_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPassword123!"

    await auth_client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Multi Request"})

    # Request 1
    await auth_client.post("/api/auth/forgot-password", json={"email": email})
    token1 = test_delivery_adapter.dispatches[0]["token"]

    # Request 2
    await auth_client.post("/api/auth/forgot-password", json={"email": email})
    token2 = test_delivery_adapter.dispatches[1]["token"]

    # Token 1 must now be invalid
    fail_resp = await auth_client.post("/api/auth/reset-password", json={"token": token1, "new_password": "NewPassword123!"})
    assert fail_resp.status_code == 401
    assert fail_resp.json()["error"]["message"] == "Invalid or expired password reset token"

    # Token 2 succeeds
    succ_resp = await auth_client.post("/api/auth/reset-password", json={"token": token2, "new_password": "NewPassword123!"})
    assert succ_resp.status_code == 200


@pytest.mark.asyncio
async def test_unrelated_user_session_unaffected_by_password_reset(
    auth_client: AsyncClient,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify resetting User A's password does NOT revoke User B's active refresh session."""
    user_a = f"usera_{uuid.uuid4().hex[:8]}@example.com"
    user_b = f"userb_{uuid.uuid4().hex[:8]}@example.com"
    pw = "CommonInitPassword123!"

    await auth_client.post("/api/auth/register", json={"email": user_a, "password": pw, "display_name": "User A"})
    await auth_client.post("/api/auth/register", json={"email": user_b, "password": pw, "display_name": "User B"})

    # Both login
    resp_a = await auth_client.post("/api/auth/login", json={"email": user_a, "password": pw})
    resp_b = await auth_client.post("/api/auth/login", json={"email": user_b, "password": pw})
    rb = resp_b.json()["refresh_token"]

    # User A resets password
    await auth_client.post("/api/auth/forgot-password", json={"email": user_a})
    token_a = test_delivery_adapter.dispatches[0]["token"]
    await auth_client.post("/api/auth/reset-password", json={"token": token_a, "new_password": "UserANewPassword123!"})

    # User B's refresh token must remain completely valid!
    ref_b = await auth_client.post("/api/auth/refresh", json={"refresh_token": rb})
    assert ref_b.status_code == 200
    assert ref_b.json()["refresh_token"]


@pytest.mark.asyncio
async def test_concurrent_reset_password_same_token_live_postgresql(
    test_app: FastAPI,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Live PostgreSQL concurrency race:

    Two simultaneous reset-password requests presenting the SAME token.
    Required invariant: exactly one HTTP 200, exactly one HTTP 401.
    """
    email = f"race_reset_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Race User"})
        await client.post("/api/auth/forgot-password", json={"email": email})
        raw_token = test_delivery_adapter.dispatches[0]["token"]

        async def _call_reset() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post(
                    "/api/auth/reset-password",
                    json={"token": raw_token, "new_password": "NewConcurrentPassword1!"},
                )
                return res.status_code

        results = await asyncio.gather(_call_reset(), _call_reset())
        assert sorted(results) == [200, 401]


@pytest.mark.asyncio
async def test_concurrent_forgot_password_requests_live_postgresql(
    test_app: FastAPI,
    db_session: AsyncSession,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Live PostgreSQL concurrency race:

    Two simultaneous forgot-password requests for the same user.
    Required invariant: both succeed (200), and only ONE token survives unconsumed in DB.
    """
    email = f"race_forgot_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Race User"})

        async def _call_forgot() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/forgot-password", json={"email": email})
                return res.status_code

        results = await asyncio.gather(_call_forgot(), _call_forgot())
        assert results == [200, 200]

        # Query user ID
        stmt_user = select(User.id).where(User.email_normalized == email.lower())
        user_id = (await db_session.execute(stmt_user)).scalar_one()

        # Check DB: exactly one unconsumed token exists
        stmt_active = select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        active_tokens = (await db_session.execute(stmt_active)).scalars().all()
        assert len(active_tokens) == 1, f"Expected exactly 1 active token, found {len(active_tokens)}"


@pytest.mark.asyncio
async def test_reset_vs_concurrent_refresh_race_live_postgresql(
    test_app: FastAPI,
    db_session: AsyncSession,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify reset vs refresh race condition on live PostgreSQL:

    Final invariant:
    After password reset completes, 0 active refresh tokens survive that were
    created before or rotated concurrently during the reset.
    """
    email = f"race_reset_ref_{uuid.uuid4().hex[:8]}@example.com"
    password = "InitialPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/auth/register", json={"email": email, "password": password, "display_name": "Race User"})
        login_resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        r1 = login_resp.json()["refresh_token"]

        await client.post("/api/auth/forgot-password", json={"email": email})
        reset_token = test_delivery_adapter.dispatches[0]["token"]

        async def _call_reset() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post(
                    "/api/auth/reset-password",
                    json={"token": reset_token, "new_password": "NewSecretPassword2026!"},
                )
                return res.status_code

        async def _call_refresh() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/refresh", json={"refresh_token": r1})
                return res.status_code

        reset_status, ref_status = await asyncio.gather(_call_reset(), _call_refresh())
        assert reset_status == 200
        assert ref_status in (200, 401)

        stmt_user = select(User.id).where(User.email_normalized == email.lower())
        user_id = (await db_session.execute(stmt_user)).scalar_one()

        # Check for ANY active tokens for that user
        stmt_active = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        active_tokens = (await db_session.execute(stmt_active)).scalars().all()
        assert len(active_tokens) == 0, f"Expected 0 active tokens, found {len(active_tokens)}"


class _FailingDeliveryAdapter:
    async def deliver_password_reset_token(self, email: str, reset_token: str) -> None:
        raise OSError("SMTP relay unavailable")


@pytest.mark.asyncio
async def test_forgot_password_delivery_failure_keeps_uniform_response(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Delivery failure must not turn into a 500 that reveals the account exists (FIX-004)."""
    set_delivery_adapter(_FailingDeliveryAdapter())
    try:
        email = f"deliveryfail_{uuid.uuid4().hex[:8]}@example.com"
        await auth_client.post(
            "/api/auth/register",
            json={"email": email, "password": "InitialPassword123!", "display_name": "Delivery Fail"},
        )
        existing = await auth_client.post("/api/auth/forgot-password", json={"email": email})
        missing = await auth_client.post(
            "/api/auth/forgot-password", json={"email": f"missing_{email}"}
        )
        assert existing.status_code == missing.status_code == 200
        assert existing.json() == missing.json()

        user = (await db_session.execute(select(User).where(User.email_normalized == email))).scalar_one()
        tokens = (
            await db_session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        ).scalars().all()
        assert len(tokens) == 1
    finally:
        set_delivery_adapter(InMemoryPasswordResetDeliveryAdapter())

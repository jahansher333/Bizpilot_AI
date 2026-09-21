"""Integration tests for Refresh Token API and Rotation (AUTH-005)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.refresh import hash_refresh_token


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
async def test_refresh_successful_rotation_end_to_end(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify standard single-use rotation: R1 -> R2, verifying database state and access."""
    email = f"refresh_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    # 1. Register & Login
    reg_resp = await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Refresh Tester"},
    )
    assert reg_resp.status_code == 202

    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    r1 = login_data["refresh_token"]
    assert r1

    # Inspect R1 in database
    r1_hash = hash_refresh_token(r1)
    stmt_r1 = select(RefreshToken).where(RefreshToken.token_hash == r1_hash)
    db_r1 = (await db_session.execute(stmt_r1)).scalar_one()
    assert db_r1.revoked_at is None
    family_id = db_r1.token_family_id
    family_expires_at = db_r1.expires_at

    # 2. Rotate R1 -> R2
    refresh_resp = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": r1},
    )
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    r2 = refresh_data["refresh_token"]
    a2 = refresh_data["access_token"]
    assert r2 != r1
    assert refresh_data["token_type"] == "bearer"
    assert refresh_data["expires_in"] == 900

    # 3. Verify A2 grants access to /api/auth/me
    me_resp = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {a2}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 4. Verify DB state: R1 revoked, R2 active, identical family and expires_at
    await db_session.refresh(db_r1)
    assert db_r1.revoked_at is not None

    r2_hash = hash_refresh_token(r2)
    stmt_r2 = select(RefreshToken).where(RefreshToken.token_hash == r2_hash)
    db_r2 = (await db_session.execute(stmt_r2)).scalar_one()
    assert db_r2.revoked_at is None
    assert db_r2.token_family_id == family_id
    assert db_r2.expires_at == family_expires_at


@pytest.mark.asyncio
async def test_refresh_multiple_sequential_rotations_preserve_ceiling(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify sequential rotations (R1 -> R2 -> R3) maintain same family and absolute expiration."""
    email = f"seq_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Seq Tester"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    current_refresh = login_resp.json()["refresh_token"]

    tokens = [current_refresh]
    for _ in range(3):
        resp = await auth_client.post(
            "/api/auth/refresh",
            json={"refresh_token": current_refresh},
        )
        assert resp.status_code == 200
        current_refresh = resp.json()["refresh_token"]
        tokens.append(current_refresh)

    # Check all 4 tokens in DB
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash.in_([hash_refresh_token(t) for t in tokens])
    )
    db_tokens = (await db_session.execute(stmt)).scalars().all()
    assert len(db_tokens) == 4

    # All share identical family ID and expires_at
    family_ids = {t.token_family_id for t in db_tokens}
    expires_ats = {t.expires_at for t in db_tokens}
    assert len(family_ids) == 1
    assert len(expires_ats) == 1

    # First 3 tokens revoked, only the 4th is active
    revoked_count = sum(1 for t in db_tokens if t.revoked_at is not None)
    active_count = sum(1 for t in db_tokens if t.revoked_at is None)
    assert revoked_count == 3
    assert active_count == 1


@pytest.mark.asyncio
async def test_refresh_replay_detection_revokes_entire_family(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify replaying an already-consumed token invalidates the entire token family."""
    email = f"replay_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Replay Tester"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    r1 = login_resp.json()["refresh_token"]

    # Legitimate rotation R1 -> R2
    rot_resp = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": r1},
    )
    assert rot_resp.status_code == 200
    r2 = rot_resp.json()["refresh_token"]

    # Malicious replay: presenting consumed R1 again
    replay_resp = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": r1},
    )
    assert replay_resp.status_code == 401
    body = replay_resp.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert body["error"]["message"] == "Invalid or expired refresh token"

    # Verify R2 is NOW REVOKED in DB as well
    r2_hash = hash_refresh_token(r2)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == r2_hash)
    db_r2 = (await db_session.execute(stmt)).scalar_one()
    assert db_r2.revoked_at is not None

    # Now presenting R2 also fails
    r2_resp = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": r2},
    )
    assert r2_resp.status_code == 401
    assert r2_resp.json()["error"]["message"] == "Invalid or expired refresh token"


@pytest.mark.asyncio
async def test_refresh_multiple_devices_independent_families(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify multiple logins create distinct families; compromise in Family A does not break Family B."""
    email = f"multidev_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "MultiDev"},
    )

    # Login 1 (Device A)
    resp_a = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r_a1 = resp_a.json()["refresh_token"]

    # Login 2 (Device B)
    resp_b = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r_b1 = resp_b.json()["refresh_token"]

    # Rotate Device A: r_a1 -> r_a2
    rot_a = await auth_client.post("/api/auth/refresh", json={"refresh_token": r_a1})
    assert rot_a.status_code == 200
    r_a2 = rot_a.json()["refresh_token"]

    # Replay r_a1 on Device A -> invalidates Family A
    replay_a = await auth_client.post("/api/auth/refresh", json={"refresh_token": r_a1})
    assert replay_a.status_code == 401

    # Device B (Family B) remains unharmed and can rotate successfully
    rot_b = await auth_client.post("/api/auth/refresh", json={"refresh_token": r_b1})
    assert rot_b.status_code == 200
    assert rot_b.json()["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_expired_token_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify expired refresh token returns 401."""
    email = f"exp_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Expired Tester"},
    )
    login_resp = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r1 = login_resp.json()["refresh_token"]

    # Expire token in database
    r1_hash = hash_refresh_token(r1)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == r1_hash)
    db_r1 = (await db_session.execute(stmt)).scalar_one()
    db_r1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    resp = await auth_client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid or expired refresh token"


@pytest.mark.asyncio
async def test_refresh_disabled_user_rejected_non_enumerating(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify inactive/disabled user returns uniform 401 on refresh."""
    email = f"disrefresh_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Disabled Refresh"},
    )
    login_resp = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r1 = login_resp.json()["refresh_token"]

    # Disable user
    stmt = select(User).where(User.email_normalized == email)
    user = (await db_session.execute(stmt)).scalar_one()
    user.status = UserStatus.DISABLED.value
    await db_session.commit()

    resp = await auth_client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert resp.json()["error"]["message"] == "Invalid or expired refresh token"


@pytest.mark.asyncio
async def test_refresh_concurrent_race_condition(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Verify strict PostgreSQL row locking on concurrent refresh requests:

    When two requests attempt to rotate the same token R1 simultaneously:
    - Request A locks row, completes rotation R1 -> R2.
    - Request B acquires lock after A commits, sees R1 revoked, triggers replay detection,
      revokes the entire family (including R2), and returns 401.
    """
    email = f"race_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    # Create user and login
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg_resp = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": "Race User"},
        )
        assert reg_resp.status_code == 202

        login_resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        r1 = login_resp.json()["refresh_token"]

        # Run two concurrent refresh requests presenting identical R1
        async def _call_refresh() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/refresh", json={"refresh_token": r1})
                return res.status_code

        results = await asyncio.gather(_call_refresh(), _call_refresh())
        assert sorted(results) == [200, 401]

"""Integration tests for User Logout and Session Revocation (AUTH-006)."""

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
from app.modules.auth.models import RefreshToken
from app.modules.auth.refresh import hash_refresh_token
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


@pytest.mark.asyncio
async def test_current_session_logout_revokes_family_and_blocks_refresh(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify standard current logout: invalidates entire family so refresh is blocked."""
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    # 1. Register & Login
    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Logout Tester"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    r1 = refresh_cookie(login_resp)

    # Rotate once: R1 -> R2
    rot_resp = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r1))
    assert rot_resp.status_code == 200
    r2 = refresh_cookie(rot_resp)

    # 2. Logout current session using R2
    logout_resp = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(r2))
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {
        "status": "success",
        "message": "Logged out successfully",
    }

    # 3. Verify DB state: both R1 and R2 are now revoked
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash.in_([hash_refresh_token(r1), hash_refresh_token(r2)])
    )
    tokens = (await db_session.execute(stmt)).scalars().all()
    assert len(tokens) == 2
    assert all(t.revoked_at is not None for t in tokens)

    # 4. Subsequent refresh with R2 must fail
    refresh_fail = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r2))
    assert refresh_fail.status_code == 401
    assert refresh_fail.json()["error"]["message"] == "Invalid or expired refresh token"


@pytest.mark.asyncio
async def test_multi_device_isolation_logout_family_a_preserves_family_b(
    auth_client: AsyncClient,
) -> None:
    """Verify logging out Device A does not invalidate Device B's independent session family."""
    email = f"multidev_lo_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "MultiDev User"},
    )

    # Device A Login
    resp_a = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r_a = refresh_cookie(resp_a)

    # Device B Login
    resp_b = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r_b = refresh_cookie(resp_b)

    # Logout Device A
    logout_a = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(r_a))
    assert logout_a.status_code == 200

    # Device A refresh is denied
    ref_a = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r_a))
    assert ref_a.status_code == 401

    # Device B remains active and can rotate successfully
    ref_b = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r_b))
    assert ref_b.status_code == 200
    assert refresh_cookie(ref_b)


@pytest.mark.asyncio
async def test_logout_current_session_idempotent(auth_client: AsyncClient) -> None:
    """Verify repeated logout with same token succeeds idempotently."""
    email = f"idem_lo_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Idem User"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    r1 = refresh_cookie(login_resp)

    # First logout
    res1 = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(r1))
    assert res1.status_code == 200

    # Second logout with same token
    res2 = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(r1))
    assert res2.status_code == 200
    assert res2.json() == {
        "status": "success",
        "message": "Logged out successfully",
    }


@pytest.mark.asyncio
async def test_logout_all_devices_revokes_all_user_families(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify POST /api/auth/logout-all revokes all sessions belonging to the authenticated user."""
    email = f"loall_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "LogoutAll User"},
    )

    # 3 distinct logins representing 3 devices
    resp1 = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    jwt1 = resp1.json()["access_token"]
    r1 = refresh_cookie(resp1)

    resp2 = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r2 = refresh_cookie(resp2)

    resp3 = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r3 = refresh_cookie(resp3)

    # Call /logout-all using jwt1
    logout_all_resp = await auth_client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    assert logout_all_resp.status_code == 200
    assert logout_all_resp.json() == {
        "status": "success",
        "message": "All sessions logged out successfully",
    }

    # Verify DB: all 3 tokens are revoked
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash.in_([
            hash_refresh_token(r1),
            hash_refresh_token(r2),
            hash_refresh_token(r3),
        ])
    )
    tokens = (await db_session.execute(stmt)).scalars().all()
    assert len(tokens) == 3
    assert all(t.revoked_at is not None for t in tokens)

    # All 3 devices are denied refresh
    assert (await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r1))).status_code == 401
    assert (await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r2))).status_code == 401
    assert (await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(r3))).status_code == 401

    # Repeated logout-all succeeds idempotently
    repeat = await auth_client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    assert repeat.status_code == 200


@pytest.mark.asyncio
async def test_access_jwt_lifecycle_after_logout(auth_client: AsyncClient) -> None:
    """Verify stateless access token remains valid until TTL expires, while refresh is immediately severed."""
    email = f"jwt_life_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "JWT Life User"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_resp.json()["access_token"]
    refresh_token = refresh_cookie(login_resp)

    # Logout
    logout_resp = await auth_client.post("/api/auth/logout", headers=refresh_cookie_header(refresh_token))
    assert logout_resp.status_code == 200

    # Access JWT can still access /me within its 15-minute window
    me_resp = await auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # But refresh is irrevocably blocked
    ref_resp = await auth_client.post("/api/auth/refresh", headers=refresh_cookie_header(refresh_token))
    assert ref_resp.status_code == 401


# -----------------------------------------------------------------------------
# Concurrency Tests against Live PostgreSQL
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_logout_vs_refresh_on_same_token(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Verify concurrency safety when logout races with refresh on the same token:

    Final invariant:
    Regardless of interleaving, NO valid/unrevoked refresh token survives in that family.
    """
    email = f"race_lor_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": "Race User"},
        )
        login_resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        r1 = refresh_cookie(login_resp)

        # Concurrently call logout and refresh presenting identical R1
        async def _call_logout() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/logout", headers=refresh_cookie_header(r1))
                return res.status_code

        async def _call_refresh() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/refresh", headers=refresh_cookie_header(r1))
                return res.status_code

        logout_status, refresh_status = await asyncio.gather(_call_logout(), _call_refresh())

        # Logout must always succeed (200)
        assert logout_status == 200
        # Refresh is either 200 (if it won race before logout) or 401 (if logout won race)
        assert refresh_status in (200, 401)

        # CRITICAL INVARIANT: In the database, all tokens belonging to this family MUST be revoked
        r1_hash = hash_refresh_token(r1)
        stmt_family = select(RefreshToken.token_family_id).where(RefreshToken.token_hash == r1_hash)
        family_id = (await db_session.execute(stmt_family)).scalar_one()

        stmt_active = select(RefreshToken).where(
            RefreshToken.token_family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        active_tokens = (await db_session.execute(stmt_active)).scalars().all()
        assert len(active_tokens) == 0, f"Expected 0 active tokens, found {len(active_tokens)}"


@pytest.mark.asyncio
async def test_concurrent_simultaneous_logouts_on_same_token(test_app: FastAPI, session_db_url: str) -> None:
    """Verify two simultaneous logouts presenting the same token both succeed cleanly."""
    email = f"race_duallo_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": "DualLogout"},
        )
        login_resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        r1 = refresh_cookie(login_resp)

        async def _call_logout() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/logout", headers=refresh_cookie_header(r1))
                return res.status_code

        res1, res2 = await asyncio.gather(_call_logout(), _call_logout())
        assert res1 == 200
        assert res2 == 200


@pytest.mark.asyncio
async def test_concurrent_logout_all_vs_refresh(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Verify concurrency safety between logout-all and refresh:

    Final invariant:
    After logout-all completes, NO active refresh token survives for that user.
    """
    email = f"race_loall_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": "Race LoAll"},
        )
        login_resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        jwt_token = login_resp.json()["access_token"]
        r1 = refresh_cookie(login_resp)

        async def _call_logout_all() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post(
                    "/api/auth/logout-all",
                    headers={"Authorization": f"Bearer {jwt_token}"},
                )
                return res.status_code

        async def _call_refresh() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/refresh", headers=refresh_cookie_header(r1))
                return res.status_code

        lo_status, ref_status = await asyncio.gather(_call_logout_all(), _call_refresh())
        assert lo_status == 200
        assert ref_status in (200, 401)

        # Query user in DB
        r1_hash = hash_refresh_token(r1)
        stmt_user = select(RefreshToken.user_id).where(RefreshToken.token_hash == r1_hash)
        user_id = (await db_session.execute(stmt_user)).scalar_one()

        # Check for ANY active tokens for that user
        stmt_active = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        active_tokens = (await db_session.execute(stmt_active)).scalars().all()
        # If refresh happened to commit after logout-all's update scanned, let's check:
        assert len(active_tokens) == 0, f"Expected 0 active tokens, found {len(active_tokens)}"

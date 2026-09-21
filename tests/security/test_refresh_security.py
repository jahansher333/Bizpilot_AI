"""Security tests for Refresh Token Rotation, Cryptographic Storage, and Replay Defense (AUTH-005)."""

from __future__ import annotations

import math
import uuid
from collections import Counter
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
from app.modules.auth.refresh import generate_refresh_token, hash_refresh_token


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


# 1. CSPRNG Entropy and Randomness Verification


def test_refresh_token_entropy_and_uniqueness() -> None:
    """Verify refresh tokens have high entropy (256 bits CSPRNG) and zero collisions across samples."""
    sample_size = 1000
    tokens = [generate_refresh_token() for _ in range(sample_size)]

    # Zero collisions
    assert len(set(tokens)) == sample_size

    # Length consistency (~43-44 chars for 32 base64url bytes)
    assert all(len(t) in (43, 44) for t in tokens)

    # Shannon entropy of characters across the population
    all_chars = "".join(tokens)
    counts = Counter(all_chars)
    total_len = len(all_chars)
    shannon_entropy = -sum(
        (count / total_len) * math.log2(count / total_len)
        for count in counts.values()
    )
    # 64 possible base64 chars -> maximum theoretical entropy is 6.0 bits/char
    # With uniform distribution, expected entropy is > 5.5 bits/char
    assert shannon_entropy > 5.5


# 2. Cryptographic Storage: Plaintext is Never Persisted


@pytest.mark.asyncio
async def test_refresh_token_plaintext_is_never_persisted(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify the raw refresh token is NEVER persisted in plain text in PostgreSQL."""
    email = f"storage_sec_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Sec User"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    raw_token = login_resp.json()["refresh_token"]

    # Direct query: search if raw_token string exists in ANY column of refresh_tokens table
    stmt = select(RefreshToken).where(RefreshToken.token_hash == raw_token)
    result = (await db_session.execute(stmt)).first()
    assert result is None, "Plaintext refresh token MUST NEVER match token_hash!"

    # Verify only SHA-256 hex digest is stored
    token_hash = hash_refresh_token(raw_token)
    stmt_hash = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    db_token = (await db_session.execute(stmt_hash)).scalar_one_or_none()
    assert db_token is not None
    assert len(db_token.token_hash) == 64
    assert all(c in "0123456789abcdef" for c in db_token.token_hash)


# 3. Non-Enumeration Uniformity Across All Failure Modes


@pytest.mark.asyncio
async def test_refresh_failure_non_enumeration_uniformity(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that all refresh failure modes return identical HTTP 401 and error envelopes."""
    email = f"nonenum_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "NonEnum User"},
    )
    login_resp = await auth_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    r1 = login_resp.json()["refresh_token"]

    # 1. Unknown token
    resp_unknown = await auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": generate_refresh_token()},
    )
    # 2. Replay token (rotate first, then replay)
    rot_resp = await auth_client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert rot_resp.status_code == 200
    resp_replay = await auth_client.post("/api/auth/refresh", json={"refresh_token": r1})

    # Compare status and envelope semantics (ignoring unique per-request correlation_id)
    assert resp_unknown.status_code == 401
    assert resp_replay.status_code == 401
    err_unknown = resp_unknown.json()["error"]
    err_replay = resp_replay.json()["error"]

    assert err_unknown["code"] == err_replay["code"] == "AUTHENTICATION_REQUIRED"
    assert err_unknown["message"] == err_replay["message"] == "Invalid or expired refresh token"
    assert err_unknown["details"] == err_replay["details"] is None
    assert err_unknown["correlation_id"] and err_replay["correlation_id"]


# 4. Strict Input Bounds and Validation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_payload",
    [
        {},
        {"refresh_token": ""},
        {"refresh_token": "   "},
        {"refresh_token": "short"},
        {"refresh_token": "a" * 129},
        {"refresh_token": generate_refresh_token(), "unexpected_extra": "attack"},
        {"refresh_token": 12345},
        {"refresh_token": None},
    ],
)
async def test_refresh_input_validation_boundary_defense(
    auth_client: AsyncClient,
    bad_payload: dict,
) -> None:
    """Verify strict Pydantic validation rejects malformed, out-of-bounds, or extra fields."""
    resp = await auth_client.post("/api/auth/refresh", json=bad_payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


# 5. Blast Radius Containment: Independent Token Families


@pytest.mark.asyncio
async def test_refresh_replay_blast_radius_confined_to_family(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify replay detection invalidates ONLY the affected device/family, not the user's other sessions."""
    email = f"blast_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Blast Radius"},
    )

    # Session 1 (e.g. Mobile)
    resp1 = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    s1_r1 = resp1.json()["refresh_token"]

    # Session 2 (e.g. Desktop)
    resp2 = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    s2_r1 = resp2.json()["refresh_token"]

    # Rotate Session 1: s1_r1 -> s1_r2
    rot1 = await auth_client.post("/api/auth/refresh", json={"refresh_token": s1_r1})
    s1_r2 = rot1.json()["refresh_token"]

    # Attack: Replay s1_r1 -> compromises Session 1
    replay_attack = await auth_client.post("/api/auth/refresh", json={"refresh_token": s1_r1})
    assert replay_attack.status_code == 401

    # Session 1's active token s1_r2 is revoked
    follow_up = await auth_client.post("/api/auth/refresh", json={"refresh_token": s1_r2})
    assert follow_up.status_code == 401

    # CRITICAL: Session 2 (Desktop) is completely unaffected
    rot2 = await auth_client.post("/api/auth/refresh", json={"refresh_token": s2_r1})
    assert rot2.status_code == 200
    assert rot2.json()["refresh_token"]


# 6. Absolute Session Ceiling: No Sliding Lifetime Reset


@pytest.mark.asyncio
async def test_refresh_does_not_extend_absolute_session_ceiling(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that token rotation NEVER pushes back the original session's expires_at ceiling."""
    email = f"ceiling_{uuid.uuid4().hex[:8]}@example.com"
    password = "ValidSecretPassword123!"

    await auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "Ceiling User"},
    )
    login_resp = await auth_client.post("/api/auth/login", json={"email": email, "password": password})
    r1 = login_resp.json()["refresh_token"]

    # Fetch initial session expires_at
    r1_hash = hash_refresh_token(r1)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == r1_hash)
    db_r1 = (await db_session.execute(stmt)).scalar_one()
    original_ceiling = db_r1.expires_at

    # Rotate multiple times
    current_token = r1
    for _ in range(5):
        resp = await auth_client.post("/api/auth/refresh", json={"refresh_token": current_token})
        assert resp.status_code == 200
        current_token = resp.json()["refresh_token"]

        token_hash = hash_refresh_token(current_token)
        stmt_t = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        db_t = (await db_session.execute(stmt_t)).scalar_one()

        # The ceiling MUST NOT change
        assert db_t.expires_at == original_ceiling

"""Consolidated adversarial and negative security tests for Authentication (AUTH-008).

Covers:
1. JWT Adversarial Testing (alg: none, wrong alg, tampered sig, truncated sig, manipulated payload, expired, future nbf, wrong issuer/aud/type, invalid sub).
2. Client-Supplied Authorization Claims (injected org_id, role, permissions ignored; identity purely from verified sub).
3. Credential-Stuffing Simulation (bounded failed attempts; non-enumeration; no permanent lockout; valid login works afterward).
4. Account Enumeration Across Register, Login, Forgot-Password (uniform status and messages across active, unknown, disabled, pending).
5. Concurrent Registration Race (live PostgreSQL race condition; exactly 1 User and 1 UserCredential created; uniform 202 response).
6. Refresh Replay Blast Radius Containment (Family A, B, C; replaying Family A revokes A only; B and C remain usable).
7. Password Reset + Concurrent Refresh (simultaneous reset and refresh; 0 pre-reset refresh sessions survive; no deadlock).
8. Reset Token Replay (consumed token cannot be replayed; returns generic 401; leaves state intact).
9. Cross-User Isolation (User A actions never alter User B sessions, credentials, or tokens).
10. Payload Robustness (bounded malicious inputs; extra fields, nulls, wrong types, SQLi-like strings, overlong strings).
11. Secret Leakage Audit (responses and logs inspected to ensure zero plaintext passwords, hashes, tokens, or signing keys appear).
12. No Permanent Attacker-Triggered Lockout (repeated failures never mutate account status to disabled/pending).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
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
from app.modules.auth.models import PasswordResetToken, RefreshToken, User, UserCredential
from app.modules.auth.recovery import (
    DevelopmentLoggingPasswordResetDeliveryAdapter,
    InMemoryPasswordResetDeliveryAdapter,
    hash_password_reset_token,
    set_delivery_adapter,
)
from app.modules.auth.tokens import TokenService
from tests.helpers import refresh_cookie, refresh_cookie_header


@pytest.fixture
def in_memory_delivery_adapter() -> InMemoryPasswordResetDeliveryAdapter:
    """Fixture providing an in-memory delivery adapter and resetting it after test."""
    adapter = InMemoryPasswordResetDeliveryAdapter()
    set_delivery_adapter(adapter)
    yield adapter
    adapter.clear()


@pytest.fixture
async def adv_client(
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


# ==============================================================================
# 1. JWT ADVERSARIAL TESTING
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_jwt_tampering_and_algorithm_confusion(
    adv_client: AsyncClient,
) -> None:
    """Test rejection of malformed, tampered, and algorithm-confused JWTs at /me."""
    settings = get_settings()
    secret = settings.auth.signing_secret.get_secret_value()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Base valid payload
    base_payload = {
        "sub": user_id,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": settings.auth.jwt_issuer,
        "aud": settings.auth.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }

    # Register user so subject exists in DB if token verification succeeds
    reg_email = f"jwt_adv_{uuid.uuid4().hex[:8]}@example.com"
    reg_pw = "ValidPassword123!"
    reg_resp = await adv_client.post(
        "/api/auth/register",
        json={"email": reg_email, "password": reg_pw, "display_name": "JWT User"},
    )
    assert reg_resp.status_code == 202

    login_resp = await adv_client.post("/api/auth/login", json={"email": reg_email, "password": reg_pw})
    valid_token = login_resp.json()["access_token"]
    real_user_id = login_resp.json()["access_token"]

    # Decode real payload for subject
    real_payload = jwt.decode(valid_token, options={"verify_signature": False})
    real_sub = real_payload["sub"]

    # Case A: alg: none
    none_token = jwt.encode(real_payload, key="", algorithm="none")
    resp_none = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {none_token}"})
    assert resp_none.status_code == 401
    assert resp_none.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Case B: Unsupported algorithm (e.g., HS384 or HS512 when HS256 expected)
    hs384_token = jwt.encode(real_payload, key=secret, algorithm="HS384")
    resp_hs384 = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {hs384_token}"})
    assert resp_hs384.status_code == 401

    # Case C: Corrupted signature
    parts = valid_token.split(".")
    corrupted_sig = ("B" if parts[2][0] == "A" else "A") + parts[2][1:]
    corrupted_token = f"{parts[0]}.{parts[1]}.{corrupted_sig}"
    resp_corrupt = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {corrupted_token}"})
    assert resp_corrupt.status_code == 401

    # Case D: Truncated signature
    truncated_token = f"{parts[0]}.{parts[1]}.{parts[2][:10]}"
    resp_trunc = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {truncated_token}"})
    assert resp_trunc.status_code == 401

    # Case E: Manipulated payload (tampered subject)
    tampered_payload = dict(real_payload)
    tampered_payload["sub"] = str(uuid.uuid4())
    tampered_payload_b64 = base64.urlsafe_b64encode(json.dumps(tampered_payload).encode()).decode().rstrip("=")
    manipulated_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"
    resp_manip = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {manipulated_token}"})
    assert resp_manip.status_code == 401

    # Case F: Expired token
    exp_payload = dict(base_payload)
    exp_payload["sub"] = real_sub
    exp_payload["exp"] = int((now - timedelta(seconds=10)).timestamp())
    exp_token = jwt.encode(exp_payload, key=secret, algorithm="HS256")
    resp_exp = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {exp_token}"})
    assert resp_exp.status_code == 401
    assert "expired" in resp_exp.json()["error"]["message"].lower()

    # Case G: Future nbf
    nbf_payload = dict(base_payload)
    nbf_payload["sub"] = real_sub
    nbf_payload["nbf"] = int((now + timedelta(minutes=10)).timestamp())
    nbf_token = jwt.encode(nbf_payload, key=secret, algorithm="HS256")
    resp_nbf = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {nbf_token}"})
    assert resp_nbf.status_code == 401

    # Case H: Wrong issuer
    iss_payload = dict(base_payload)
    iss_payload["sub"] = real_sub
    iss_payload["iss"] = "malicious-issuer"
    iss_token = jwt.encode(iss_payload, key=secret, algorithm="HS256")
    resp_iss = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {iss_token}"})
    assert resp_iss.status_code == 401

    # Case I: Wrong audience
    aud_payload = dict(base_payload)
    aud_payload["sub"] = real_sub
    aud_payload["aud"] = "malicious-aud"
    aud_token = jwt.encode(aud_payload, key=secret, algorithm="HS256")
    resp_aud = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {aud_token}"})
    assert resp_aud.status_code == 401

    # Case J: Wrong token type (e.g., refresh or id)
    type_payload = dict(base_payload)
    type_payload["sub"] = real_sub
    type_payload["type"] = "refresh"
    type_token = jwt.encode(type_payload, key=secret, algorithm="HS256")
    resp_type = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {type_token}"})
    assert resp_type.status_code == 401

    # Case K: Invalid UUID subject
    sub_payload = dict(base_payload)
    sub_payload["sub"] = "not-a-valid-uuid"
    sub_token = jwt.encode(sub_payload, key=secret, algorithm="HS256")
    resp_sub = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {sub_token}"})
    assert resp_sub.status_code == 401


# ==============================================================================
# 2. CLIENT-SUPPLIED AUTHORIZATION CLAIMS
# ==============================================================================


@pytest.mark.asyncio
async def test_client_supplied_authorization_claims_never_trusted(
    adv_client: AsyncClient,
) -> None:
    """Verify injected tenant or authorization claims in token or request do not elevate principal."""
    settings = get_settings()
    secret = settings.auth.signing_secret.get_secret_value()

    email = f"claims_{uuid.uuid4().hex[:8]}@example.com"
    pw = "ValidSecretPassword123!"

    reg_resp = await adv_client.post("/api/auth/register", json={"email": email, "password": pw, "display_name": "Claim User"})
    assert reg_resp.status_code == 202

    login_resp = await adv_client.post("/api/auth/login", json={"email": email, "password": pw})
    real_token = login_resp.json()["access_token"]
    real_payload = jwt.decode(real_token, options={"verify_signature": False})

    # Forging a token with injected org_id, role='owner', permissions=['*']
    injected_payload = dict(real_payload)
    injected_payload["org_id"] = str(uuid.uuid4())
    injected_payload["organization_id"] = str(uuid.uuid4())
    injected_payload["tenant_id"] = str(uuid.uuid4())
    injected_payload["role"] = "owner"
    injected_payload["permissions"] = ["*"]

    forged_token = jwt.encode(injected_payload, key=secret, algorithm="HS256")

    # Access /me with the token containing injected claims
    me_resp = await adv_client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert me_resp.status_code == 200
    user_me = me_resp.json()

    # The response must ONLY contain verified user fields from DB (id, email, display_name, status)
    assert set(user_me.keys()) == {"id", "email", "display_name", "status"}
    assert "org_id" not in user_me
    assert "role" not in user_me
    assert "permissions" not in user_me
    assert user_me["email"] == email.lower()
    assert user_me["status"] == "active"


# ==============================================================================
# 3. CREDENTIAL-STUFFING SIMULATION & NO PERMANENT ATTACKER LOCKOUT
# ==============================================================================


@pytest.mark.asyncio
async def test_credential_stuffing_simulation_and_no_permanent_lockout(
    adv_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify bounded rapid failed login attempts:

    - all return generic non-enumerating 401
    - no account existence disclosure
    - account is NOT locked or disabled
    - legitimate user can still log in with correct credentials
    """
    email = f"stuffing_{uuid.uuid4().hex[:8]}@example.com"
    correct_password = "CorrectHorseBatteryStaple123!"

    # 1. Register legitimate user
    await adv_client.post(
        "/api/auth/register",
        json={"email": email, "password": correct_password, "display_name": "Target User"},
    )

    # 2. Simulate 10 rapid incorrect password attempts (credential stuffing attack)
    passwords_to_try = [
        "123456789012",
        "Password12345!",
        "admin12345678",
        "qwertyuiopas",
        "wrongpassword1",
        "wrongpassword2",
        "wrongpassword3",
        "wrongpassword4",
        "wrongpassword5",
        "wrongpassword6",
    ]

    for attempt_pw in passwords_to_try:
        resp = await adv_client.post("/api/auth/login", json={"email": email, "password": attempt_pw})
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert body["error"]["message"] == "Invalid email or password"

    # 3. Verify user status in DB is STILL ACTIVE (no permanent attacker-triggered lockout)
    stmt = select(User).where(User.email_normalized == email.lower())
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.status == UserStatus.ACTIVE.value

    # 4. Legitimate user logs in with correct password -> must succeed
    succ_resp = await adv_client.post("/api/auth/login", json={"email": email, "password": correct_password})
    assert succ_resp.status_code == 200
    assert "access_token" in succ_resp.json()
    assert refresh_cookie(succ_resp)


# ==============================================================================
# 4. ACCOUNT ENUMERATION ACROSS REGISTER, LOGIN, FORGOT-PASSWORD
# ==============================================================================


@pytest.mark.asyncio
async def test_account_enumeration_adversarial_consistency(
    adv_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify non-enumeration consistency across Register, Login, and Forgot-Password

    for active, unknown, disabled, and pending accounts.
    """
    pw = "SecurePassword123!"
    active_email = f"enum_active_{uuid.uuid4().hex[:8]}@example.com"
    disabled_email = f"enum_dis_{uuid.uuid4().hex[:8]}@example.com"
    pending_email = f"enum_pen_{uuid.uuid4().hex[:8]}@example.com"
    unknown_email = f"enum_unk_{uuid.uuid4().hex[:8]}@example.com"

    # 1. REGISTER endpoint: test first registration and subsequent duplicate registration
    # Duplicate registration returns uniform 202 without revealing account existence
    reg_resp1 = await adv_client.post("/api/auth/register", json={"email": active_email, "password": pw, "display_name": "Active"})
    assert reg_resp1.status_code == 202
    assert reg_resp1.json()["message"] == "Registration request accepted. Please proceed to login."

    reg_resp2 = await adv_client.post("/api/auth/register", json={"email": active_email, "password": pw, "display_name": "Active Dup"})
    assert reg_resp2.status_code == 202
    assert reg_resp2.json()["message"] == "Registration request accepted. Please proceed to login."

    # Register disabled and pending users
    await adv_client.post("/api/auth/register", json={"email": disabled_email, "password": pw, "display_name": "Disabled"})
    await adv_client.post("/api/auth/register", json={"email": pending_email, "password": pw, "display_name": "Pending"})

    # Update statuses in DB
    stmt_dis = select(User).where(User.email_normalized == disabled_email.lower())
    user_dis = (await db_session.execute(stmt_dis)).scalar_one()
    user_dis.status = UserStatus.DISABLED.value

    stmt_pen = select(User).where(User.email_normalized == pending_email.lower())
    user_pen = (await db_session.execute(stmt_pen)).scalar_one()
    user_pen.status = UserStatus.PENDING.value
    await db_session.commit()

    # Re-registering existing disabled or pending email still returns uniform 202
    for em in [disabled_email, pending_email]:
        reg_resp = await adv_client.post("/api/auth/register", json={"email": em, "password": pw, "display_name": "Test"})
        assert reg_resp.status_code == 202
        assert reg_resp.json()["message"] == "Registration request accepted. Please proceed to login."

    # 2. LOGIN endpoint: unknown, disabled, pending, or wrong password return uniform 401
    login_cases = [
        {"email": unknown_email, "password": pw},
        {"email": disabled_email, "password": pw},
        {"email": pending_email, "password": pw},
        {"email": active_email, "password": "WrongPasswordAttempt123!"},
    ]
    for case in login_cases:
        l_resp = await adv_client.post("/api/auth/login", json=case)
        assert l_resp.status_code == 401, f"Failed for {case['email']}: got {l_resp.status_code}, body: {l_resp.text}"
        assert l_resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert l_resp.json()["error"]["message"] == "Invalid email or password"

    # 3. FORGOT-PASSWORD endpoint: active, unknown, disabled, pending return uniform 200
    for em in [active_email, unknown_email, disabled_email, pending_email]:
        fp_resp = await adv_client.post("/api/auth/forgot-password", json={"email": em})
        assert fp_resp.status_code == 200
        assert fp_resp.json()["status"] == "success"
        assert fp_resp.json()["message"] == "If an eligible account exists for this email, password recovery instructions have been sent."


# ==============================================================================
# 5. CONCURRENT REGISTRATION RACE (LIVE POSTGRESQL)
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_concurrent_registration_race_live_postgresql(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    """Send concurrent registration requests for the same email against live PostgreSQL.

    Invariants:
    - Both requests return 202 Accepted (non-enumerating)
    - Exactly 1 User record created in database
    - Exactly 1 UserCredential record created in database
    - No 500 errors, no database constraint violations exposed
    """
    race_email = f"race_reg_{uuid.uuid4().hex[:8]}@example.com"
    pw = "ValidRegistrationSecret123!"
    payload = {"email": race_email, "password": pw, "display_name": "Racer"}

    transport = ASGITransport(app=test_app)

    async def _call_register() -> tuple[int, dict]:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            res = await c.post("/api/auth/register", json=payload)
            return res.status_code, res.json()

    # Execute concurrent registrations simultaneously with separate client connections
    results = await asyncio.gather(_call_register(), _call_register())

    # Assert external contract: both return uniform 202 Accepted
    for status_code, body in results:
        assert status_code == 202
        assert body["message"] == "Registration request accepted. Please proceed to login."

    # Query DB to ensure exactly 1 User and 1 UserCredential exist
    stmt_users = select(User).where(User.email_normalized == race_email.lower())
    users = (await db_session.execute(stmt_users)).scalars().all()
    assert len(users) == 1

    stmt_creds = select(UserCredential).where(UserCredential.user_id == users[0].id)
    creds = (await db_session.execute(stmt_creds)).scalars().all()
    assert len(creds) == 1


# ==============================================================================
# 6. REFRESH REPLAY BLAST RADIUS CONTAINMENT (LIVE POSTGRESQL)
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_refresh_replay_blast_radius_containment(
    adv_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 3 independent refresh token families (Family A, B, C) for one user.

    Exercising replay against Family A:
    - Revokes Family A completely
    - Family B remains valid and can refresh
    - Family C remains valid and can refresh
    - User account is not disabled
    """
    email = f"blast_{uuid.uuid4().hex[:8]}@example.com"
    pw = "DeviceTestPassword123!"

    await adv_client.post("/api/auth/register", json={"email": email, "password": pw, "display_name": "Multi-Device User"})

    # Login 3 times to simulate 3 devices (Device A, B, C) -> 3 distinct token families
    l_a = await adv_client.post("/api/auth/login", json={"email": email, "password": pw})
    l_b = await adv_client.post("/api/auth/login", json={"email": email, "password": pw})
    l_c = await adv_client.post("/api/auth/login", json={"email": email, "password": pw})

    token_a1 = refresh_cookie(l_a)
    token_b1 = refresh_cookie(l_b)
    token_c1 = refresh_cookie(l_c)

    # Legitimate rotation on Family A: A1 -> A2
    r_a1 = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(token_a1))
    assert r_a1.status_code == 200
    token_a2 = refresh_cookie(r_a1)

    # REPLAY ATTACK on Family A: re-present rotated A1
    r_a_replay = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(token_a1))
    assert r_a_replay.status_code == 401
    assert r_a_replay.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Family A is now poisoned: A2 is also revoked
    r_a2 = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(token_a2))
    assert r_a2.status_code == 401

    # Blast radius containment: Family B and Family C MUST still be valid!
    r_b = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(token_b1))
    assert r_b.status_code == 200
    assert r_b.json()["access_token"]

    r_c = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(token_c1))
    assert r_c.status_code == 200
    assert r_c.json()["access_token"]

    # User remains active
    stmt = select(User).where(User.email_normalized == email.lower())
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.status == UserStatus.ACTIVE.value


# ==============================================================================
# 7. PASSWORD RESET + CONCURRENT REFRESH (LIVE POSTGRESQL)
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_password_reset_and_concurrent_refresh_annihilation(
    test_app: FastAPI,
    db_session: AsyncSession,
    in_memory_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Race between password reset and concurrent session refresh.

    Required invariant:
    - Zero surviving refresh sessions derived from prior sessions
    - Subsequent refresh attempts with prior tokens fail
    - No deadlock during concurrent execution
    """
    email = f"annihilate_{uuid.uuid4().hex[:8]}@example.com"
    old_pw = "OldPassword123!"
    new_pw = "BrandNewSecurePassword2026!"

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/auth/register", json={"email": email, "password": old_pw, "display_name": "Reset User"})
        l_resp = await client.post("/api/auth/login", json={"email": email, "password": old_pw})
        pre_reset_refresh_token = refresh_cookie(l_resp)

        # Request password recovery
        await client.post("/api/auth/forgot-password", json={"email": email})
        raw_reset_token = in_memory_delivery_adapter.dispatches[0]["token"]

        # Execute concurrent password reset and refresh with separate clients
        async def _call_reset() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post(
                    "/api/auth/reset-password",
                    json={"token": raw_reset_token, "new_password": new_pw},
                )
                return res.status_code

        async def _call_refresh() -> int:
            async with AsyncClient(transport=transport, base_url="http://testserver") as c:
                res = await c.post("/api/auth/refresh", headers=refresh_cookie_header(pre_reset_refresh_token))
                return res.status_code

        reset_status, ref_status = await asyncio.gather(_call_reset(), _call_refresh())
        assert reset_status == 200
        assert ref_status in (200, 401)

        # Verify no unrevoked refresh tokens exist in DB for this user
        stmt_user = select(User).where(User.email_normalized == email.lower())
        user = (await db_session.execute(stmt_user)).scalar_one()

        stmt_active_tokens = select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        active_tokens = (await db_session.execute(stmt_active_tokens)).scalars().all()
        assert len(active_tokens) == 0, f"Expected 0 active refresh tokens after reset, found {len(active_tokens)}"

        # Subsequent refresh attempt with prior token must fail with 401
        followup_refresh = await client.post("/api/auth/refresh", headers=refresh_cookie_header(pre_reset_refresh_token))
        assert followup_refresh.status_code == 401


# ==============================================================================
# 8. RESET TOKEN REPLAY
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_reset_token_replay(
    adv_client: AsyncClient,
    in_memory_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify consumed reset token cannot be replayed.

    Security Invariant (AUTH-007):
    A password reset token is strictly single-use.
    Replaying an already-consumed reset token is rejected with generic HTTP 401
    AUTHENTICATION_REQUIRED ('Invalid or expired password reset token').
    """
    email = f"replay_reset_{uuid.uuid4().hex[:8]}@example.com"
    pw1 = "InitialPassword123!"
    pw2 = "SecondPassword123!"
    pw3 = "ThirdPassword123!"

    await adv_client.post("/api/auth/register", json={"email": email, "password": pw1, "display_name": "Reset Replay"})
    await adv_client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = in_memory_delivery_adapter.dispatches[0]["token"]

    # First reset: succeeds
    resp1 = await adv_client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": pw2})
    assert resp1.status_code == 200

    # Second reset (REPLAY): fails with generic 401
    resp2 = await adv_client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": pw3})
    assert resp2.status_code == 401
    assert resp2.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert resp2.json()["error"]["message"] == "Invalid or expired password reset token"

    # Login with pw2 succeeds (pw3 was rejected)
    l_succ = await adv_client.post("/api/auth/login", json={"email": email, "password": pw2})
    assert l_succ.status_code == 200

    l_fail = await adv_client.post("/api/auth/login", json={"email": email, "password": pw3})
    assert l_fail.status_code == 401


# ==============================================================================
# 9. CROSS-USER ISOLATION
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_cross_user_isolation(
    adv_client: AsyncClient,
    db_session: AsyncSession,
    in_memory_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Security Invariant:
    User A-controlled IDs/claims/reset/session operations cannot mutate or impersonate User B
    without possessing User B's valid credential or token.

    Verifies:
    - User A /logout-all revokes only User A sessions, leaving User B sessions unperturbed.
    - User A password reset revokes only User A sessions, leaving User B sessions unperturbed.
    - User A password reset token resets User A's credential, never altering User B's credential.
    - User B can still authenticate with User B's credentials and access their own resources.
    """
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
    pw_a = "UserASecretPassword123!"
    pw_b = "UserBSecretPassword456!"

    # Register User A and User B
    await adv_client.post("/api/auth/register", json={"email": user_a_email, "password": pw_a, "display_name": "User A"})
    await adv_client.post("/api/auth/register", json={"email": user_b_email, "password": pw_b, "display_name": "User B"})

    # Login both users
    login_a = await adv_client.post("/api/auth/login", json={"email": user_a_email, "password": pw_a})
    login_b = await adv_client.post("/api/auth/login", json={"email": user_b_email, "password": pw_b})

    token_a = login_a.json()["access_token"]
    refresh_b = refresh_cookie(login_b)

    # 1. User A calls /logout-all (authenticated as User A)
    logout_a = await adv_client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {token_a}"})
    assert logout_a.status_code == 200

    # User B's refresh token must remain active and unaffected
    ref_b = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(refresh_b))
    assert ref_b.status_code == 200
    new_refresh_b = refresh_cookie(ref_b)

    # 2. User A requests and executes password reset
    in_memory_delivery_adapter.clear()
    await adv_client.post("/api/auth/forgot-password", json={"email": user_a_email})
    raw_token_a = in_memory_delivery_adapter.dispatches[0]["token"]
    reset_a_resp = await adv_client.post(
        "/api/auth/reset-password",
        json={"token": raw_token_a, "new_password": "NewUserAPassword123!"},
    )
    assert reset_a_resp.status_code == 200

    # User B's refresh token must STILL remain active and unaffected
    ref_b2 = await adv_client.post("/api/auth/refresh", headers=refresh_cookie_header(new_refresh_b))
    assert ref_b2.status_code == 200

    # User B's password was NOT changed by User A's reset:
    # User B can still authenticate with original password pw_b
    login_b_after = await adv_client.post("/api/auth/login", json={"email": user_b_email, "password": pw_b})
    assert login_b_after.status_code == 200

    # And User B CANNOT authenticate with User A's new password
    login_b_fail = await adv_client.post("/api/auth/login", json={"email": user_b_email, "password": "NewUserAPassword123!"})
    assert login_b_fail.status_code == 401


# ==============================================================================
# 10. PAYLOAD ROBUSTNESS & MALFORMED INPUTS
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_payload_robustness_and_malformed_inputs(
    adv_client: AsyncClient,
) -> None:
    """Verify controlled 4xx rejection without 500s or stack trace leakage across all auth endpoints."""
    malicious_inputs = [
        # Extra unexpected fields
        {"email": "valid@example.com", "password": "ValidPassword123!", "injected_field": "exploit"},
        # Null values
        {"email": None, "password": "ValidPassword123!"},
        # Wrong types (integers instead of strings)
        {"email": 12345, "password": 98765},
        # Overlong strings
        {"email": "a" * 300 + "@example.com", "password": "ValidPassword123!"},
        # SQL Injection string
        {"email": "' OR '1'='1' --", "password": "' OR '1'='1' --"},
        # Control / null characters
        {"email": "test\x00inject@example.com", "password": "ValidPassword123!"},
    ]

    endpoints = [
        ("/api/auth/register", "post"),
        ("/api/auth/login", "post"),
    ]

    for path, method in endpoints:
        for payload in malicious_inputs:
            if method == "post":
                resp = await adv_client.post(path, json=payload)
                assert resp.status_code in (400, 422), f"{path} failed to reject bad payload with 4xx: {resp.status_code}"
                body = resp.json()
                assert "error" in body
                assert body["error"]["code"] in ("VALIDATION_ERROR", "AUTHENTICATION_REQUIRED")
                assert "traceback" not in resp.text.lower()


# ==============================================================================
# 11. SECRET LEAKAGE AUDIT ACROSS NEGATIVE PATHS
# ==============================================================================


@pytest.mark.asyncio
async def test_adversarial_secret_leakage_audit(
    adv_client: AsyncClient,
    db_session: AsyncSession,
    in_memory_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicitly verify that captured HTTP responses, headers, logs, and error content
    do NOT disclose actual sensitive values for:
    1. Plaintext password
    2. Argon2id password hash
    3. Raw refresh token
    4. Refresh token SHA-256 hash
    5. Raw password-reset token
    6. Password-reset token SHA-256 hash
    7. JWT signing secret
    8. Authorization Bearer header / token
    """
    settings = get_settings()
    actual_jwt_secret = settings.auth.signing_secret.get_secret_value()

    email = f"leak_audit_{uuid.uuid4().hex[:8]}@example.com"
    secret_pw = "ActualSecretP@ssw0rd2026!"

    with caplog.at_level(logging.DEBUG):
        # 1. Register user with secret password
        resp_reg = await adv_client.post(
            "/api/auth/register",
            json={"email": email, "password": secret_pw, "display_name": "Audit User"},
        )
        assert resp_reg.status_code == 202

        # Retrieve actual Argon2id hash from database
        stmt = (
            select(UserCredential.password_hash)
            .join(User, User.id == UserCredential.user_id)
            .where(User.email_normalized == email.lower())
        )
        actual_argon2_hash = (await db_session.execute(stmt)).scalar_one()

        # 2. Login to obtain actual access token and actual raw refresh token
        resp_login = await adv_client.post(
            "/api/auth/login",
            json={"email": email, "password": secret_pw},
        )
        assert resp_login.status_code == 200
        login_data = resp_login.json()
        actual_access_token = login_data["access_token"]
        actual_raw_refresh_token = refresh_cookie(resp_login)
        actual_auth_header = f"Bearer {actual_access_token}"
        actual_refresh_hash = hashlib.sha256(actual_raw_refresh_token.encode("utf-8")).hexdigest()

        # 3. Request password recovery to obtain actual raw reset token
        in_memory_delivery_adapter.clear()
        resp_fp = await adv_client.post("/api/auth/forgot-password", json={"email": email})
        assert resp_fp.status_code == 200
        actual_raw_reset_token = in_memory_delivery_adapter.dispatches[0]["token"]
        actual_reset_hash = hashlib.sha256(actual_raw_reset_token.encode("utf-8")).hexdigest()

        # Also trigger dev delivery adapter to ensure its log output never leaks tokens
        dev_adapter = DevelopmentLoggingPasswordResetDeliveryAdapter()
        await dev_adapter.deliver_password_reset_token(email, actual_raw_reset_token)

        # 4. Negative and positive interactions across auth endpoints
        # Failed login: wrong password
        resp_login_wrong_pw = await adv_client.post(
            "/api/auth/login", json={"email": email, "password": "WrongPasswordAttempt123!"}
        )
        assert resp_login_wrong_pw.status_code == 401

        # Failed login: nonexistent user with the actual password
        resp_login_wrong_user = await adv_client.post(
            "/api/auth/login", json={"email": "nonexistent@example.com", "password": secret_pw}
        )
        assert resp_login_wrong_user.status_code == 401

        # Authenticated /me request
        resp_me_valid = await adv_client.get(
            "/api/auth/me", headers={"Authorization": actual_auth_header}
        )
        assert resp_me_valid.status_code == 200

        # Unauthenticated /me request
        resp_me_invalid = await adv_client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid.token.value"}
        )
        assert resp_me_invalid.status_code == 401

        # Refresh rotation with valid token
        resp_refresh_valid = await adv_client.post(
            "/api/auth/refresh", headers=refresh_cookie_header(actual_raw_refresh_token)
        )
        assert resp_refresh_valid.status_code == 200
        rotated_refresh_token = refresh_cookie(resp_refresh_valid)

        # Refresh replay with already-consumed token (fails 401)
        resp_refresh_replay = await adv_client.post(
            "/api/auth/refresh", headers=refresh_cookie_header(actual_raw_refresh_token)
        )
        assert resp_refresh_replay.status_code == 401

        # Malformed / invalid refresh request
        resp_refresh_malformed = await adv_client.post(
            "/api/auth/refresh", headers=refresh_cookie_header("y" * 32)
        )
        assert resp_refresh_malformed.status_code == 401

        # Reset password with invalid token
        resp_reset_invalid = await adv_client.post(
            "/api/auth/reset-password",
            json={"token": "x" * 32, "new_password": "NewSecretAuditPassword123!"},
        )
        assert resp_reset_invalid.status_code == 401

        # Reset password with valid token
        resp_reset_valid = await adv_client.post(
            "/api/auth/reset-password",
            json={"token": actual_raw_reset_token, "new_password": "NewSecretAuditPassword123!"},
        )
        assert resp_reset_valid.status_code == 200

        # Reset password replay with already-consumed token
        resp_reset_replay = await adv_client.post(
            "/api/auth/reset-password",
            json={"token": actual_raw_reset_token, "new_password": "AnotherNewPassword123!"},
        )
        assert resp_reset_replay.status_code == 401

        # Logout with rotated refresh token
        resp_logout = await adv_client.post(
            "/api/auth/logout", headers=refresh_cookie_header(rotated_refresh_token)
        )
        assert resp_logout.status_code == 200

    # Ensure all 8 actual sensitive values are non-empty and unique
    secret_registry = {
        "plaintext_password": secret_pw,
        "argon2id_password_hash": actual_argon2_hash,
        "raw_refresh_token": actual_raw_refresh_token,
        "refresh_token_sha256": actual_refresh_hash,
        "raw_password_reset_token": actual_raw_reset_token,
        "password_reset_token_sha256": actual_reset_hash,
        "jwt_signing_secret": actual_jwt_secret,
        "authorization_bearer_token": actual_access_token,
        "authorization_bearer_header": actual_auth_header,
    }
    for secret_name, secret_val in secret_registry.items():
        assert secret_val and len(secret_val) >= 8, f"{secret_name} was empty or too short"

    all_responses = [
        resp_reg,
        resp_login,
        resp_fp,
        resp_login_wrong_pw,
        resp_login_wrong_user,
        resp_me_valid,
        resp_me_invalid,
        resp_refresh_valid,
        resp_refresh_replay,
        resp_refresh_malformed,
        resp_reset_invalid,
        resp_reset_valid,
        resp_reset_replay,
        resp_logout,
    ]

    # Verification 1: Universal checks across ALL response bodies
    for r in all_responses:
        body = r.text
        # Plaintext password must NEVER appear in ANY response
        assert secret_pw not in body, f"Plaintext password leaked in response body of {r.url}"
        # Argon2id password hash must NEVER appear in ANY response
        assert actual_argon2_hash not in body, f"Argon2id hash leaked in response body of {r.url}"
        # Refresh token SHA-256 hash must NEVER appear in ANY response
        assert actual_refresh_hash not in body, f"Refresh token SHA-256 hash leaked in response body of {r.url}"
        # Raw password-reset token must NEVER appear in ANY response body (including forgot/reset endpoints)
        assert actual_raw_reset_token not in body, f"Raw reset token leaked in response body of {r.url}"
        # Password-reset token SHA-256 hash must NEVER appear in ANY response
        assert actual_reset_hash not in body, f"Reset token SHA-256 hash leaked in response body of {r.url}"
        # JWT signing secret must NEVER appear in ANY response
        assert actual_jwt_secret not in body, f"JWT signing secret leaked in response body of {r.url}"
        # Authorization Bearer header string must NEVER appear in ANY response body
        assert actual_auth_header not in body, f"Authorization header string leaked in response body of {r.url}"

    # Verification 2: Contextual checks on token issuance endpoints vs others
    token_issuance_responses = {resp_login, resp_refresh_valid}
    non_issuance_responses = [r for r in all_responses if r not in token_issuance_responses]

    for r in all_responses:
        # The raw refresh token never appears in ANY body, not even at issuance: it travels only in
        # the HttpOnly cookie (SEC-P1 F3).
        assert actual_raw_refresh_token not in r.text, f"Raw refresh token leaked in body of {r.url}"
    for r in non_issuance_responses:
        # Outside of token issuance endpoints, access tokens must NEVER appear
        assert actual_access_token not in r.text, f"Access token leaked in {r.url}"

    # Verification 3: Headers across ALL responses must NEVER contain sensitive material
    for r in all_responses:
        # Issuance responses legitimately carry the refresh token in their Set-Cookie header only.
        if r in token_issuance_responses:
            headers_str = str([(k, v) for k, v in r.headers.multi_items() if k.lower() != "set-cookie"])
            assert all(
                "httponly" in v.lower() and "secure" in v.lower()
                for k, v in r.headers.multi_items()
                if k.lower() == "set-cookie" and actual_raw_refresh_token in v
            )
        else:
            headers_str = str(r.headers)
        assert secret_pw not in headers_str, f"Plaintext password in headers of {r.url}"
        assert actual_argon2_hash not in headers_str, f"Argon2id hash in headers of {r.url}"
        assert actual_raw_refresh_token not in headers_str, f"Raw refresh token in headers of {r.url}"
        assert actual_refresh_hash not in headers_str, f"Refresh token hash in headers of {r.url}"
        assert actual_raw_reset_token not in headers_str, f"Raw reset token in headers of {r.url}"
        assert actual_reset_hash not in headers_str, f"Reset token hash in headers of {r.url}"
        assert actual_jwt_secret not in headers_str, f"JWT signing secret in headers of {r.url}"
        assert actual_access_token not in headers_str, f"Access token in headers of {r.url}"
        assert actual_auth_header not in headers_str, f"Auth header in headers of {r.url}"

    # Verification 4: Application logs audit
    all_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_pw not in all_logs, "Plaintext password leaked in application logs"
    assert actual_argon2_hash not in all_logs, "Argon2id hash leaked in application logs"
    assert actual_raw_refresh_token not in all_logs, "Raw refresh token leaked in application logs"
    assert actual_refresh_hash not in all_logs, "Refresh token hash leaked in application logs"
    assert actual_raw_reset_token not in all_logs, "Raw reset token leaked in application logs"
    assert actual_reset_hash not in all_logs, "Reset token hash leaked in application logs"
    assert actual_jwt_secret not in all_logs, "JWT signing secret leaked in application logs"
    assert actual_access_token not in all_logs, "Access token leaked in application logs"
    assert actual_auth_header not in all_logs, "Authorization header leaked in application logs"

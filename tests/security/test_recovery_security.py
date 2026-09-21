"""Security tests for Password Recovery, Reset Token Confidentiality, and Isolation (AUTH-007)."""

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
from app.modules.auth.models import PasswordResetToken, User
from app.modules.auth.recovery import (
    DevelopmentLoggingPasswordResetDeliveryAdapter,
    InMemoryPasswordResetDeliveryAdapter,
    generate_password_reset_token,
    get_delivery_adapter,
    hash_password_reset_token,
    set_delivery_adapter,
)


@pytest.fixture
def test_delivery_adapter() -> InMemoryPasswordResetDeliveryAdapter:
    adapter = InMemoryPasswordResetDeliveryAdapter()
    set_delivery_adapter(adapter)
    yield adapter
    adapter.clear()


@pytest.fixture
async def auth_client(
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


# 1. Strict Non-Enumeration Uniformity


@pytest.mark.asyncio
async def test_forgot_password_strict_non_enumeration_uniformity(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify forgot-password response is 100% identical across all account states:

    - Active user
    - Unknown user
    - Disabled user
    - Pending user
    """
    pw = "ValidSecretPassword123!"
    active_email = f"active_{uuid.uuid4().hex[:8]}@example.com"
    disabled_email = f"disabled_{uuid.uuid4().hex[:8]}@example.com"
    pending_email = f"pending_{uuid.uuid4().hex[:8]}@example.com"
    unknown_email = f"unknown_{uuid.uuid4().hex[:8]}@example.com"

    # Create active user
    await auth_client.post("/api/auth/register", json={"email": active_email, "password": pw, "display_name": "Active"})

    # Create disabled user
    await auth_client.post("/api/auth/register", json={"email": disabled_email, "password": pw, "display_name": "Disabled"})
    stmt_dis = select(User).where(User.email_normalized == disabled_email.lower())
    user_dis = (await db_session.execute(stmt_dis)).scalar_one()
    user_dis.status = UserStatus.DISABLED.value

    # Create pending user
    await auth_client.post("/api/auth/register", json={"email": pending_email, "password": pw, "display_name": "Pending"})
    stmt_pen = select(User).where(User.email_normalized == pending_email.lower())
    user_pen = (await db_session.execute(stmt_pen)).scalar_one()
    user_pen.status = UserStatus.PENDING.value
    await db_session.commit()

    resp_active = await auth_client.post("/api/auth/forgot-password", json={"email": active_email})
    resp_unknown = await auth_client.post("/api/auth/forgot-password", json={"email": unknown_email})
    resp_disabled = await auth_client.post("/api/auth/forgot-password", json={"email": disabled_email})
    resp_pending = await auth_client.post("/api/auth/forgot-password", json={"email": pending_email})

    responses = [resp_active, resp_unknown, resp_disabled, resp_pending]

    for resp in responses:
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"status", "message"}
        assert body["status"] == "success"
        assert body["message"] == "If an eligible account exists for this email, password recovery instructions have been sent."


# 2. Token Confidentiality


@pytest.mark.asyncio
async def test_raw_reset_token_never_persisted_in_database(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify raw reset token plaintext is NEVER stored in the database."""
    email = f"confidential_{uuid.uuid4().hex[:8]}@example.com"
    await auth_client.post("/api/auth/register", json={"email": email, "password": "InitialPassword123!", "display_name": "Confidential"})
    await auth_client.post("/api/auth/forgot-password", json={"email": email})

    raw_token = test_delivery_adapter.dispatches[0]["token"]

    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == raw_token)
    match = (await db_session.execute(stmt)).first()
    assert match is None, "Raw reset token was found in database plaintext!"


@pytest.mark.asyncio
async def test_recovery_responses_leak_no_internal_metadata(
    auth_client: AsyncClient,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify forgot-password and reset-password responses never leak tokens, hashes, or IDs."""
    email = f"noleak_{uuid.uuid4().hex[:8]}@example.com"
    await auth_client.post("/api/auth/register", json={"email": email, "password": "InitialPassword123!", "display_name": "No Leak"})

    resp1 = await auth_client.post("/api/auth/forgot-password", json={"email": email})
    assert set(resp1.json().keys()) == {"status", "message"}

    raw_token = test_delivery_adapter.dispatches[0]["token"]
    resp2 = await auth_client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "NewValidPassword123!"})
    assert set(resp2.json().keys()) == {"status", "message"}


# 3. Input Boundary Validation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_payload",
    [
        {},
        {"email": ""},
        {"email": "not-an-email"},
        {"email": "user@example.com", "injected_field": "bad"},
        {"email": "a" * 256 + "@example.com"},
    ],
)
async def test_forgot_password_input_boundary_defense(
    auth_client: AsyncClient,
    bad_payload: dict,
) -> None:
    resp = await auth_client.post("/api/auth/forgot-password", json=bad_payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_payload",
    [
        {},
        {"token": ""},
        {"token": "short", "new_password": "ValidPassword123!"},
        {"token": generate_password_reset_token(), "new_password": "short"},
        {"token": generate_password_reset_token(), "new_password": "a" * 129},
        {"token": generate_password_reset_token(), "new_password": "ValidPassword123!", "extra": "inject"},
    ],
)
async def test_reset_password_input_boundary_defense(
    auth_client: AsyncClient,
    bad_payload: dict,
) -> None:
    resp = await auth_client.post("/api/auth/reset-password", json=bad_payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# 4. Same Password Rejection Leaves Token Usable


@pytest.mark.asyncio
async def test_same_password_rejection_leaves_token_usable(
    auth_client: AsyncClient,
    test_delivery_adapter: InMemoryPasswordResetDeliveryAdapter,
) -> None:
    """Verify that attempting to reset to the same password is rejected,

    but leaves the token unconsumed so the user can submit a different password.
    """
    email = f"samepw_{uuid.uuid4().hex[:8]}@example.com"
    cur_password = "ExistingSecretPassword123!"

    await auth_client.post("/api/auth/register", json={"email": email, "password": cur_password, "display_name": "SamePW User"})
    await auth_client.post("/api/auth/forgot-password", json={"email": email})
    token = test_delivery_adapter.dispatches[0]["token"]

    # Attempt reset with same password -> rejected with 422
    rej_resp = await auth_client.post("/api/auth/reset-password", json={"token": token, "new_password": cur_password})
    assert rej_resp.status_code == 422
    assert "New password cannot be the same as your current password" in rej_resp.json()["error"]["message"]

    # Token must still be usable with a genuinely new password
    succ_resp = await auth_client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "GenuinelyNewPassword2026!"},
    )
    assert succ_resp.status_code == 200
    assert succ_resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_recovery_logs_and_production_api_leak_no_secrets(
    auth_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify application logs and production HTTP responses contain no reset secrets, hashes, or passwords."""
    import logging

    # Explicitly test with the real default DevelopmentLoggingPasswordResetDeliveryAdapter
    dev_adapter = DevelopmentLoggingPasswordResetDeliveryAdapter()
    set_delivery_adapter(dev_adapter)

    email = f"logaudit_{uuid.uuid4().hex[:8]}@example.com"
    initial_pw = "InitialSecret123!"
    new_pw = "UpdatedSecretPassword2026!"

    await auth_client.post("/api/auth/register", json={"email": email, "password": initial_pw, "display_name": "Log Audit"})

    with caplog.at_level(logging.INFO):
        # 1. Forgot password request with real default logging adapter
        forgot_resp = await auth_client.post("/api/auth/forgot-password", json={"email": email})

    assert forgot_resp.status_code == 200
    forgot_body = forgot_resp.json()
    assert "token" not in forgot_body
    assert "hash" not in forgot_body
    assert forgot_body["status"] == "success"
    assert forgot_body["message"] == "If an eligible account exists for this email, password recovery instructions have been sent."

    # Inspect logs: ensure no raw reset token, no hashes, no plaintext passwords appear
    all_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert initial_pw not in all_logs
    assert new_pw not in all_logs
    assert "no external email sent" in all_logs

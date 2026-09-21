"""Unit tests for password recovery service, token lifecycle, and delivery (AUTH-007)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationException, ValidationException
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import PasswordResetToken, User, UserCredential
from app.modules.auth.password import PasswordService
from app.modules.auth.recovery import (
    DevelopmentLoggingPasswordResetDeliveryAdapter,
    InMemoryPasswordResetDeliveryAdapter,
    LoggingPasswordResetDeliveryAdapter,
    PasswordRecoveryService,
    generate_password_reset_token,
    hash_password_reset_token,
)
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.modules.auth.service import AccountPolicyService


# Token Generation & Cryptographic Primitives


def test_generate_password_reset_token_entropy_and_format() -> None:
    token1 = generate_password_reset_token()
    token2 = generate_password_reset_token()

    assert isinstance(token1, str)
    assert len(token1) >= 42
    assert token1 != token2


def test_hash_password_reset_token_sha256_hex() -> None:
    raw = generate_password_reset_token()
    h1 = hash_password_reset_token(raw)
    h2 = hash_password_reset_token(f"  {raw}  ")

    assert len(h1) == 64
    assert h1 == h2  # whitespace stripped
    assert all(c in "0123456789abcdef" for c in h1)


# Schema Bounds & Validation


def test_forgot_password_schema_valid() -> None:
    req = ForgotPasswordRequest(email="user@example.com")
    assert req.email == "user@example.com"


def test_forgot_password_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ForgotPasswordRequest(email="user@example.com", unexpected="injected")  # type: ignore[call-arg]


def test_reset_password_schema_bounds() -> None:
    req = ResetPasswordRequest(token=generate_password_reset_token(), new_password="ValidNewPassword123!")
    assert req.new_password == "ValidNewPassword123!"

    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="short", new_password="ValidNewPassword123!")

    with pytest.raises(ValidationError):
        ResetPasswordRequest(token=generate_password_reset_token(), new_password="short")

    with pytest.raises(ValidationError):
        ResetPasswordRequest(
            token=generate_password_reset_token(),
            new_password="ValidNewPassword123!",
            extra_field="bad",  # type: ignore[call-arg]
        )


# Forgot-Password Request Flow


@pytest.mark.asyncio
async def test_forgot_password_known_active_user_creates_token_and_dispatches() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    password_svc = MagicMock(spec=PasswordService)
    delivery_adapter = InMemoryPasswordResetDeliveryAdapter()

    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="active@example.com",
        display_name="Active User",
        status=UserStatus.ACTIVE.value,
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_user_by_id_for_update.return_value = mock_user

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        delivery_adapter=delivery_adapter,
    )

    req = ForgotPasswordRequest(email="active@example.com")
    resp = await service.request_password_reset(req)

    assert isinstance(resp, ForgotPasswordResponse)
    assert resp.status == "success"
    assert "password recovery instructions have been sent" in resp.message

    # Verified lock on user
    repo.get_user_by_id_for_update.assert_awaited_once_with(user_id)
    # Verified invalidation of previous unconsumed tokens
    repo.invalidate_active_password_reset_tokens.assert_awaited_once()
    assert repo.invalidate_active_password_reset_tokens.await_args.args[0] == user_id
    # Verified token creation
    repo.create_password_reset_token.assert_awaited_once()
    # Verified delivery dispatch
    assert len(delivery_adapter.dispatches) == 1
    assert delivery_adapter.dispatches[0]["email"] == "active@example.com"
    assert len(delivery_adapter.dispatches[0]["token"]) >= 42


@pytest.mark.asyncio
async def test_forgot_password_unknown_user_uniform_response_no_delivery() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_user_by_email.return_value = None
    password_svc = MagicMock(spec=PasswordService)
    delivery_adapter = InMemoryPasswordResetDeliveryAdapter()

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        delivery_adapter=delivery_adapter,
    )

    req = ForgotPasswordRequest(email="unknown@example.com")
    resp = await service.request_password_reset(req)

    assert isinstance(resp, ForgotPasswordResponse)
    assert resp.status == "success"
    assert "password recovery instructions have been sent" in resp.message

    # Timing mitigation executed
    password_svc.verify_dummy.assert_called_once()
    # No DB token created, no delivery dispatched
    repo.create_password_reset_token.assert_not_called()
    assert len(delivery_adapter.dispatches) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.DISABLED.value, UserStatus.PENDING.value])
async def test_forgot_password_inactive_user_uniform_response_no_delivery(status: str) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    mock_user = User(
        id=uuid.uuid4(),
        email_normalized="inactive@example.com",
        display_name="Inactive User",
        status=status,
    )
    repo.get_user_by_email.return_value = mock_user
    password_svc = MagicMock(spec=PasswordService)
    delivery_adapter = InMemoryPasswordResetDeliveryAdapter()

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        delivery_adapter=delivery_adapter,
    )

    req = ForgotPasswordRequest(email="inactive@example.com")
    resp = await service.request_password_reset(req)

    assert isinstance(resp, ForgotPasswordResponse)
    assert resp.status == "success"

    # Timing mitigation executed
    password_svc.verify_dummy.assert_called_once()
    # No DB token created, no delivery dispatched
    repo.create_password_reset_token.assert_not_called()
    assert len(delivery_adapter.dispatches) == 0


# Reset-Password Completion Flow


@pytest.mark.asyncio
async def test_reset_password_success_flow() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    token_id = uuid.uuid4()
    raw_token = generate_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)
    now = datetime.now(timezone.utc)

    reset_token = PasswordResetToken(
        id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=15),
        consumed_at=None,
    )
    mock_user = User(
        id=user_id,
        email_normalized="resetuser@example.com",
        display_name="Reset User",
        status=UserStatus.ACTIVE.value,
    )
    mock_cred = UserCredential(
        user_id=user_id,
        password_hash="argon2id$old_dummy_hash",
    )

    repo.get_password_reset_token_by_hash.return_value = reset_token
    repo.get_password_reset_token_by_hash_for_update.return_value = reset_token
    repo.get_user_by_id.return_value = mock_user
    repo.get_user_by_id_for_update.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_cred

    password_svc = MagicMock(spec=PasswordService)
    password_svc.verify_password.return_value = MagicMock(valid=False)  # Not same password
    password_svc.hash_password.return_value = "argon2id$new_hash"

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        account_policy=AccountPolicyService(),
    )

    req = ResetPasswordRequest(token=raw_token, new_password="BrandNewSecurePassword123!")
    resp = await service.reset_password(req)

    assert isinstance(resp, ResetPasswordResponse)
    assert resp.status == "success"
    assert "Password reset successfully" in resp.message

    # Verified password policy & verification
    password_svc.validate_password_policy.assert_called_once_with("BrandNewSecurePassword123!")
    password_svc.verify_password.assert_called_once_with("BrandNewSecurePassword123!", "argon2id$old_dummy_hash")
    password_svc.hash_password.assert_called_once_with("BrandNewSecurePassword123!")

    # Verified persistence operations
    repo.update_password_hash.assert_awaited_once_with(user_id, "argon2id$new_hash")
    repo.consume_password_reset_token.assert_awaited_once()
    assert repo.consume_password_reset_token.await_args.args[0] == token_id
    # Verified session revocation
    repo.revoke_all_user_refresh_tokens.assert_awaited_once()
    assert repo.revoke_all_user_refresh_tokens.await_args.args[0] == user_id


@pytest.mark.asyncio
async def test_reset_password_unknown_token_rejected_generic_401() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    repo.get_password_reset_token_by_hash.return_value = None
    repo.get_password_reset_token_by_hash_for_update.return_value = None

    service = PasswordRecoveryService(session=session, repository=repo)

    req = ResetPasswordRequest(token=generate_password_reset_token(), new_password="BrandNewSecurePassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.reset_password(req)

    assert exc_info.value.message == "Invalid or expired password reset token"
    repo.update_password_hash.assert_not_called()
    repo.consume_password_reset_token.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_expired_token_rejected_generic_401() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    now = datetime.now(timezone.utc)
    expired_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=hash_password_reset_token("some_token"),
        expires_at=now - timedelta(seconds=1),
        consumed_at=None,
    )
    repo.get_password_reset_token_by_hash.return_value = expired_token
    repo.get_password_reset_token_by_hash_for_update.return_value = expired_token

    service = PasswordRecoveryService(session=session, repository=repo)

    req = ResetPasswordRequest(token=generate_password_reset_token(), new_password="BrandNewSecurePassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.reset_password(req)

    assert exc_info.value.message == "Invalid or expired password reset token"
    repo.update_password_hash.assert_not_called()
    repo.consume_password_reset_token.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_already_consumed_token_rejected_generic_401() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    now = datetime.now(timezone.utc)
    consumed_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=hash_password_reset_token("some_token"),
        expires_at=now + timedelta(minutes=10),
        consumed_at=now - timedelta(minutes=2),
    )
    repo.get_password_reset_token_by_hash.return_value = consumed_token
    repo.get_password_reset_token_by_hash_for_update.return_value = consumed_token

    service = PasswordRecoveryService(session=session, repository=repo)

    req = ResetPasswordRequest(token=generate_password_reset_token(), new_password="BrandNewSecurePassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.reset_password(req)

    assert exc_info.value.message == "Invalid or expired password reset token"
    repo.update_password_hash.assert_not_called()
    repo.consume_password_reset_token.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_same_as_current_password_rejected() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    token_id = uuid.uuid4()
    raw_token = generate_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)
    now = datetime.now(timezone.utc)

    reset_token = PasswordResetToken(
        id=token_id,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=15),
        consumed_at=None,
    )
    mock_user = User(
        id=user_id,
        email_normalized="resetuser@example.com",
        display_name="Reset User",
        status=UserStatus.ACTIVE.value,
    )
    mock_cred = UserCredential(
        user_id=user_id,
        password_hash="argon2id$same_hash",
    )

    repo.get_password_reset_token_by_hash.return_value = reset_token
    repo.get_password_reset_token_by_hash_for_update.return_value = reset_token
    repo.get_user_by_id.return_value = mock_user
    repo.get_user_by_id_for_update.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_cred

    password_svc = MagicMock(spec=PasswordService)
    password_svc.verify_password.return_value = MagicMock(valid=True)  # SAME PASSWORD MATCH!

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        account_policy=AccountPolicyService(),
    )

    req = ResetPasswordRequest(token=raw_token, new_password="SamePassword123!")
    with pytest.raises(ValidationException) as exc_info:
        await service.reset_password(req)

    assert "New password cannot be the same as your current password" in exc_info.value.message
    # Token must NOT be consumed, credentials must NOT be updated, sessions must NOT be revoked
    repo.consume_password_reset_token.assert_not_called()
    repo.update_password_hash.assert_not_called()
    repo.revoke_all_user_refresh_tokens.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.DISABLED.value, UserStatus.PENDING.value])
async def test_reset_password_inactive_user_rejected_generic_401(status: str) -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    raw_token = generate_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)
    now = datetime.now(timezone.utc)

    reset_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=15),
        consumed_at=None,
    )
    inactive_user = User(
        id=user_id,
        email_normalized="inactive@example.com",
        display_name="Inactive User",
        status=status,
    )

    repo.get_password_reset_token_by_hash.return_value = reset_token
    repo.get_password_reset_token_by_hash_for_update.return_value = reset_token
    repo.get_user_by_id.return_value = inactive_user
    repo.get_user_by_id_for_update.return_value = inactive_user

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
    )

    req = ResetPasswordRequest(token=raw_token, new_password="ValidNewPassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.reset_password(req)

    assert exc_info.value.message == "Invalid or expired password reset token"
    repo.update_password_hash.assert_not_called()
    repo.consume_password_reset_token.assert_not_called()


# Delivery Adapter Semantics & Security


@pytest.mark.asyncio
async def test_development_logging_delivery_adapter_does_not_leak_tokens_or_hashes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify development logging adapter never logs raw token, hash, or secrets."""
    import logging

    adapter = DevelopmentLoggingPasswordResetDeliveryAdapter()
    raw_token = generate_password_reset_token()
    token_hash = hash_password_reset_token(raw_token)
    email = "audit_check@example.com"

    with caplog.at_level(logging.INFO):
        await adapter.deliver_password_reset_token(email, raw_token)

    # Verify log record created
    assert any("local development dispatch recorded" in record.message for record in caplog.records)
    assert any("(no external email sent)" in record.message for record in caplog.records)

    # Verify neither raw token nor hash appears anywhere in logged text
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert raw_token not in full_log
    assert token_hash not in full_log

    # Verify backward compatible alias
    assert LoggingPasswordResetDeliveryAdapter is DevelopmentLoggingPasswordResetDeliveryAdapter


# Explicit Four-State Contract Uniformity


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    ["active", "unknown", "disabled", "pending"],
)
async def test_forgot_password_exact_contract_across_all_account_states(scenario: str) -> None:
    """Verify ACTIVE, UNKNOWN, DISABLED, and PENDING return the exact approved contract."""
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    password_svc = MagicMock(spec=PasswordService)
    delivery_adapter = InMemoryPasswordResetDeliveryAdapter()

    user_id = uuid.uuid4()
    email = f"{scenario}@example.com"

    if scenario == "active":
        user = User(
            id=user_id,
            email_normalized=email,
            display_name="User",
            status=UserStatus.ACTIVE.value,
        )
        repo.get_user_by_email.return_value = user
        repo.get_user_by_id_for_update.return_value = user
    elif scenario == "unknown":
        repo.get_user_by_email.return_value = None
    elif scenario == "disabled":
        user = User(
            id=user_id,
            email_normalized=email,
            display_name="User",
            status=UserStatus.DISABLED.value,
        )
        repo.get_user_by_email.return_value = user
    elif scenario == "pending":
        user = User(
            id=user_id,
            email_normalized=email,
            display_name="User",
            status=UserStatus.PENDING.value,
        )
        repo.get_user_by_email.return_value = user

    service = PasswordRecoveryService(
        session=session,
        repository=repo,
        password_service=password_svc,
        delivery_adapter=delivery_adapter,
    )

    req = ForgotPasswordRequest(email=email)
    resp = await service.request_password_reset(req)

    assert resp.status == "success"
    assert resp.message == "If an eligible account exists for this email, password recovery instructions have been sent."

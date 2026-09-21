"""Unit tests for RefreshService and refresh token primitives (AUTH-005)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.core.errors import AuthenticationException
from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.refresh import (
    RefreshService,
    generate_refresh_token,
    hash_refresh_token,
)
from app.modules.auth.schemas import RefreshRequest, RefreshResponse
from app.modules.auth.tokens import AccessTokenResult, TokenService


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="test-signing-secret-unit-tests-12345",
            refresh_token_days=30,
        ),
    )


@pytest.fixture
def token_service(auth_settings: Settings) -> TokenService:
    return TokenService(auth_settings)


# Primitives: Generation and Hashing


def test_generate_refresh_token_entropy_and_format() -> None:
    token1 = generate_refresh_token()
    token2 = generate_refresh_token()
    assert token1 != token2
    assert len(token1) >= 42
    # URL-safe characters only
    assert all(c.isalnum() or c in "-_" for c in token1)


def test_hash_refresh_token_sha256_hex() -> None:
    raw = "test-raw-refresh-token-string-123456"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert hash_refresh_token(raw) == expected
    assert len(hash_refresh_token(raw)) == 64


# Schema Validation


def test_refresh_request_schema_valid() -> None:
    req = RefreshRequest(refresh_token="a" * 43)
    assert req.refresh_token == "a" * 43


def test_refresh_request_schema_rejects_too_short() -> None:
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="too_short_token")


def test_refresh_request_schema_rejects_too_long() -> None:
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="a" * 129)


def test_refresh_request_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="a" * 43, extra="unexpected")  # type: ignore[call-arg]


# Domain Service: Successful Rotation


@pytest.mark.asyncio
async def test_refresh_service_successful_rotation(token_service: TokenService) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    future_exp = datetime.now(timezone.utc) + timedelta(days=25)
    existing_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=future_exp,
        revoked_at=None,
    )
    mock_user = User(
        id=user_id,
        email_normalized="user@example.com",
        display_name="Valid User",
        status=UserStatus.ACTIVE.value,
    )

    repo.get_refresh_token_by_hash_for_update.return_value = existing_token
    repo.get_user_by_id.return_value = mock_user

    service = RefreshService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = RefreshRequest(refresh_token=raw_token)
    resp = await service.refresh(req)

    assert isinstance(resp, RefreshResponse)
    assert resp.access_token
    assert resp.token_type == "bearer"
    assert resp.expires_in == 900
    assert resp.refresh_token
    assert resp.refresh_token != raw_token

    # Verify presented token was revoked
    repo.revoke_refresh_token.assert_awaited_once()
    assert repo.revoke_refresh_token.await_args.args[0] == existing_token.id

    # Verify successor token shares same family_id and absolute expires_at
    repo.create_refresh_token.assert_awaited_once()
    kwargs = repo.create_refresh_token.await_args.kwargs
    assert kwargs["user_id"] == user_id
    assert kwargs["token_family_id"] == family_id
    assert kwargs["expires_at"] == future_exp
    assert kwargs["token_hash"] == hash_refresh_token(resp.refresh_token)


# Domain Service: Non-Enumerating Unknown Token


@pytest.mark.asyncio
async def test_refresh_service_unknown_token_raises_auth_exception(
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_refresh_token_by_hash_for_update.return_value = None

    service = RefreshService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = RefreshRequest(refresh_token=generate_refresh_token())
    with pytest.raises(AuthenticationException) as exc:
        await service.refresh(req)

    assert exc.value.message == "Invalid or expired refresh token"
    repo.revoke_refresh_token.assert_not_called()
    repo.revoke_token_family.assert_not_called()
    repo.create_refresh_token.assert_not_called()


# Domain Service: Replay Detection Revokes Entire Family


@pytest.mark.asyncio
async def test_refresh_service_replay_detection_revokes_entire_family(
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    now = datetime.now(timezone.utc)
    # Token was already revoked previously (replay attempt!)
    already_revoked_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=now + timedelta(days=20),
        revoked_at=now - timedelta(minutes=5),
    )

    repo.get_refresh_token_by_hash_for_update.return_value = already_revoked_token

    service = RefreshService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = RefreshRequest(refresh_token=raw_token)
    with pytest.raises(AuthenticationException) as exc:
        await service.refresh(req)

    assert exc.value.message == "Invalid or expired refresh token"

    # Entire family MUST be revoked immediately
    repo.revoke_token_family.assert_awaited_once()
    assert repo.revoke_token_family.await_args.args[0] == family_id

    # No replacement token created
    repo.create_refresh_token.assert_not_called()


# Domain Service: Absolute Session Expiration


@pytest.mark.asyncio
async def test_refresh_service_expired_token_rejected(token_service: TokenService) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    now = datetime.now(timezone.utc)
    expired_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=now - timedelta(seconds=1),
        revoked_at=None,
    )

    repo.get_refresh_token_by_hash_for_update.return_value = expired_token

    service = RefreshService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = RefreshRequest(refresh_token=raw_token)
    with pytest.raises(AuthenticationException) as exc:
        await service.refresh(req)

    assert exc.value.message == "Invalid or expired refresh token"
    # Does NOT treat natural expiration as a malicious replay
    repo.revoke_token_family.assert_not_called()
    repo.create_refresh_token.assert_not_called()


# Domain Service: User Account Inactive Non-Enumerating


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.DISABLED.value, UserStatus.PENDING.value])
async def test_refresh_service_inactive_user_rejected_non_enumerating(
    status: str,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    future_exp = datetime.now(timezone.utc) + timedelta(days=20)
    existing_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=future_exp,
        revoked_at=None,
    )
    inactive_user = User(
        id=user_id,
        email_normalized="inactive@example.com",
        display_name="Inactive User",
        status=status,
    )

    repo.get_refresh_token_by_hash_for_update.return_value = existing_token
    repo.get_user_by_id.return_value = inactive_user

    service = RefreshService(
        session=session,
        repository=repo,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = RefreshRequest(refresh_token=raw_token)
    with pytest.raises(AuthenticationException) as exc:
        await service.refresh(req)

    assert exc.value.message == "Invalid or expired refresh token"
    # No new token issued
    repo.create_refresh_token.assert_not_called()

"""Unit tests for LogoutService and session revocation schemas (AUTH-006)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.errors import AuthenticationException
from app.modules.auth.logout import LogoutService
from app.modules.auth.models import RefreshToken
from app.modules.auth.refresh import generate_refresh_token, hash_refresh_token
from app.modules.auth.schemas import LogoutRequest, LogoutResponse


# Schema Validation


def test_logout_request_schema_valid() -> None:
    raw = generate_refresh_token()
    req = LogoutRequest(refresh_token=raw)
    assert req.refresh_token == raw


def test_logout_request_schema_rejects_too_short() -> None:
    with pytest.raises(ValidationError):
        LogoutRequest(refresh_token="short")


def test_logout_request_schema_rejects_too_long() -> None:
    with pytest.raises(ValidationError):
        LogoutRequest(refresh_token="a" * 129)


def test_logout_request_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LogoutRequest(refresh_token=generate_refresh_token(), unexpected_id="bad")  # type: ignore[call-arg]


def test_logout_response_schema_defaults() -> None:
    resp = LogoutResponse()
    assert resp.status == "success"
    assert resp.message == "Logged out successfully"


# Domain Service: Current Session Logout


@pytest.mark.asyncio
async def test_logout_current_session_success_revokes_entire_family() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    now = datetime.now(timezone.utc)
    active_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=now + timedelta(days=25),
        revoked_at=None,
    )

    repo.get_refresh_token_by_hash_for_update.return_value = active_token
    service = LogoutService(session=session, repository=repo)

    req = LogoutRequest(refresh_token=raw_token)
    resp = await service.logout_current_session(req)

    assert isinstance(resp, LogoutResponse)
    assert resp.status == "success"
    assert resp.message == "Logged out successfully"

    repo.get_refresh_token_by_hash_for_update.assert_awaited_once_with(token_hash)
    repo.revoke_token_family.assert_awaited_once()
    assert repo.revoke_token_family.await_args.args[0] == family_id
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_current_session_idempotent_when_already_revoked() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    now = datetime.now(timezone.utc)
    already_revoked_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=now + timedelta(days=20),
        revoked_at=now - timedelta(minutes=10),
    )

    repo.get_refresh_token_by_hash_for_update.return_value = already_revoked_token
    service = LogoutService(session=session, repository=repo)

    req = LogoutRequest(refresh_token=raw_token)
    resp = await service.logout_current_session(req)

    # Must be successful 200 OK without triggering replay detection
    assert isinstance(resp, LogoutResponse)
    assert resp.status == "success"
    assert resp.message == "Logged out successfully"

    repo.get_refresh_token_by_hash_for_update.assert_awaited_once_with(token_hash)
    repo.revoke_token_family.assert_awaited_once()
    assert repo.revoke_token_family.await_args.args[0] == family_id
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_current_session_unknown_token_raises_generic_auth_exception() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_refresh_token_by_hash_for_update.return_value = None

    service = LogoutService(session=session, repository=repo)

    req = LogoutRequest(refresh_token=generate_refresh_token())
    with pytest.raises(AuthenticationException) as exc_info:
        await service.logout_current_session(req)

    assert exc_info.value.message == "Invalid or expired refresh token"
    repo.revoke_token_family.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_current_session_db_failure_fails_closed() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.side_effect = RuntimeError("Database connection lost")
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    now = datetime.now(timezone.utc)
    active_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=family_id,
        expires_at=now + timedelta(days=25),
        revoked_at=None,
    )

    repo.get_refresh_token_by_hash_for_update.return_value = active_token
    service = LogoutService(session=session, repository=repo)

    req = LogoutRequest(refresh_token=raw_token)
    with pytest.raises(RuntimeError, match="Database connection lost"):
        await service.logout_current_session(req)

    session.commit.assert_not_called()


# Domain Service: Logout-All Sessions


@pytest.mark.asyncio
async def test_logout_all_sessions_success_revokes_all_active_tokens_for_user() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    repo.revoke_all_user_refresh_tokens.return_value = 3
    user_id = uuid.uuid4()

    service = LogoutService(session=session, repository=repo)
    resp = await service.logout_all_sessions(user_id)

    assert isinstance(resp, LogoutResponse)
    assert resp.status == "success"
    assert resp.message == "All sessions logged out successfully"

    repo.revoke_all_user_refresh_tokens.assert_awaited_once()
    assert repo.revoke_all_user_refresh_tokens.await_args.args[0] == user_id
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_all_sessions_zero_active_tokens_remains_successful() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    repo.revoke_all_user_refresh_tokens.return_value = 0
    user_id = uuid.uuid4()

    service = LogoutService(session=session, repository=repo)
    resp = await service.logout_all_sessions(user_id)

    assert isinstance(resp, LogoutResponse)
    assert resp.status == "success"
    assert resp.message == "All sessions logged out successfully"

    repo.revoke_all_user_refresh_tokens.assert_awaited_once()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_all_sessions_db_failure_fails_closed() -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.side_effect = RuntimeError("Database deadlocked")
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()

    service = LogoutService(session=session, repository=repo)
    with pytest.raises(RuntimeError, match="Database deadlocked"):
        await service.logout_all_sessions(user_id)

    session.commit.assert_not_called()

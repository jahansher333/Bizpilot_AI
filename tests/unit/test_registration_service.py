"""Unit tests for RegistrationService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.core.errors import ValidationException
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User
from app.modules.auth.password import PasswordService
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import RegistrationService


@pytest.fixture
def fast_password_service() -> PasswordService:
    settings = Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="test-only-signing-secret",
            argon2_time_cost=1,
            argon2_memory_cost_kib=8192,
            argon2_parallelism=1,
        ),
    )
    return PasswordService(settings)


@pytest.mark.asyncio
async def test_registration_service_successful_flow(
    fast_password_service: PasswordService,
) -> None:
    """Verify service normalizes email, checks policy, hashes password, and persists user/credential."""
    session = AsyncMock()
    # Mock begin_nested context manager
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    repo.get_user_by_email.return_value = None

    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="test@example.com",
        display_name="Test User",
        status=UserStatus.ACTIVE.value,
    )
    repo.create_user.return_value = mock_user

    service = RegistrationService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
    )

    req = RegisterRequest(
        email="  Test@Example.COM  ",
        password="ValidPassphrase123!",
        display_name="Test User",
    )

    resp = await service.register(req)

    assert resp.message == "Registration request accepted. Please proceed to login."
    repo.get_user_by_email.assert_awaited_once_with("test@example.com")
    repo.create_user.assert_awaited_once_with(
        email_normalized="test@example.com",
        display_name="Test User",
        status=UserStatus.ACTIVE,
    )
    # create_credential called with user_id and argon2id hash
    repo.create_credential.assert_awaited_once()
    call_args = repo.create_credential.await_args
    assert call_args.kwargs["user_id"] == user_id
    assert call_args.kwargs["password_hash"].startswith("$argon2id$")
    assert "ValidPassphrase123!" not in call_args.kwargs["password_hash"]


@pytest.mark.asyncio
async def test_registration_service_duplicate_pre_check_non_enumerating(
    fast_password_service: PasswordService,
) -> None:
    """Verify existing user returns uniform response and does not attempt insert."""
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_user_by_email.return_value = User(
        email_normalized="existing@example.com",
        display_name="Existing User",
    )

    pwd_service = fast_password_service
    pwd_service.verify_dummy = MagicMock(wraps=pwd_service.verify_dummy)

    service = RegistrationService(
        session=session,
        repository=repo,
        password_service=pwd_service,
    )

    req = RegisterRequest(
        email="existing@example.com",
        password="ValidPassphrase123!",
        display_name="Existing User",
    )

    resp = await service.register(req)

    assert resp.message == "Registration request accepted. Please proceed to login."
    # No user or credential creation
    repo.create_user.assert_not_called()
    repo.create_credential.assert_not_called()
    # Dummy verification executed for timing protection
    pwd_service.verify_dummy.assert_called_once()


@pytest.mark.asyncio
async def test_registration_service_concurrent_race_integrity_error_handled(
    fast_password_service: PasswordService,
) -> None:
    """Verify IntegrityError on insert race is absorbed safely without 500 or crash."""
    session = AsyncMock()
    # Mock begin_nested to raise IntegrityError on exit or entry
    nested_cm = AsyncMock()
    nested_cm.__aenter__.side_effect = IntegrityError("statement", "params", Exception("unique violation"))
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    repo.get_user_by_email.return_value = None  # Passed pre-check

    pwd_service = fast_password_service
    pwd_service.verify_dummy = MagicMock(wraps=pwd_service.verify_dummy)

    service = RegistrationService(
        session=session,
        repository=repo,
        password_service=pwd_service,
    )

    req = RegisterRequest(
        email="racing@example.com",
        password="ValidPassphrase123!",
        display_name="Racing User",
    )

    resp = await service.register(req)

    assert resp.message == "Registration request accepted. Please proceed to login."
    pwd_service.verify_dummy.assert_called_once()


@pytest.mark.asyncio
async def test_registration_service_enforces_password_policy(
    fast_password_service: PasswordService,
) -> None:
    """Verify password policy rejection occurs before database calls."""
    session = AsyncMock()
    repo = AsyncMock()

    service = RegistrationService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
    )

    # Denylisted password of valid length
    req = RegisterRequest(
        email="user@example.com",
        password="password123456",
        display_name="User",
    )

    with pytest.raises(ValidationException, match="too common or easily guessed"):
        await service.register(req)

    repo.get_user_by_email.assert_not_called()
    repo.create_user.assert_not_called()

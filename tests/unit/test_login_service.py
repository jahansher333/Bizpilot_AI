"""Unit tests for LoginService (AUTH-004)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.core.errors import AuthenticationException
from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User, UserCredential
from app.modules.auth.password import PasswordService, PasswordVerificationResult
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import LoginService
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
            argon2_time_cost=1,
            argon2_memory_cost_kib=8192,
            argon2_parallelism=1,
        ),
    )


@pytest.fixture
def fast_password_service(auth_settings: Settings) -> PasswordService:
    return PasswordService(auth_settings)


@pytest.fixture
def token_service(auth_settings: Settings) -> TokenService:
    return TokenService(auth_settings)


@pytest.mark.asyncio
async def test_login_service_successful_flow(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="owner@example.com",
        display_name="Business Owner",
        status=UserStatus.ACTIVE.value,
    )
    raw_password = "CorrectPassword123!"
    password_hash = fast_password_service.hash_password(raw_password)
    mock_credential = UserCredential(
        user_id=user_id,
        password_hash=password_hash,
    )

    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_credential

    service = LoginService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="  Owner@Example.COM  ", password=raw_password)
    resp = await service.login(req)

    assert resp.access_token
    assert resp.token_type == "bearer"
    assert resp.expires_in == 900
    assert resp.refresh_token

    repo.get_user_by_email.assert_awaited_once_with("owner@example.com")
    repo.get_credential_by_user_id.assert_awaited_once_with(user_id)
    repo.update_last_login_at.assert_awaited_once()
    assert repo.update_last_login_at.await_args.args[0] == user_id
    repo.create_refresh_token.assert_awaited_once()
    assert repo.create_refresh_token.await_args.kwargs["user_id"] == user_id




@pytest.mark.asyncio
async def test_login_service_unknown_email_non_enumerating(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.get_user_by_email.return_value = None

    pwd_service = fast_password_service
    pwd_service.verify_dummy = MagicMock(wraps=pwd_service.verify_dummy)

    service = LoginService(
        session=session,
        repository=repo,
        password_service=pwd_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="unknown@example.com", password="SomePassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.login(req)

    assert exc_info.value.message == "Invalid email or password"
    pwd_service.verify_dummy.assert_called_once()
    repo.get_credential_by_user_id.assert_not_called()
    repo.update_last_login_at.assert_not_called()


@pytest.mark.asyncio
async def test_login_service_missing_credential_anomaly_non_enumerating(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="nocred@example.com",
        display_name="No Cred User",
        status=UserStatus.ACTIVE.value,
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = None

    pwd_service = fast_password_service
    pwd_service.verify_dummy = MagicMock(wraps=pwd_service.verify_dummy)

    service = LoginService(
        session=session,
        repository=repo,
        password_service=pwd_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="nocred@example.com", password="SomePassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.login(req)

    assert exc_info.value.message == "Invalid email or password"
    pwd_service.verify_dummy.assert_called_once()
    repo.update_last_login_at.assert_not_called()


@pytest.mark.asyncio
async def test_login_service_wrong_password_non_enumerating(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="user@example.com",
        display_name="User",
        status=UserStatus.ACTIVE.value,
    )
    password_hash = fast_password_service.hash_password("RealPassword123!")
    mock_credential = UserCredential(
        user_id=user_id,
        password_hash=password_hash,
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_credential

    service = LoginService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="user@example.com", password="WrongPassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.login(req)

    assert exc_info.value.message == "Invalid email or password"
    repo.update_last_login_at.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.DISABLED.value, UserStatus.PENDING.value])
async def test_login_service_inactive_account_non_enumerating(
    status: str,
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="inactive@example.com",
        display_name="Inactive User",
        status=status,
    )
    password_hash = fast_password_service.hash_password("RealPassword123!")
    mock_credential = UserCredential(
        user_id=user_id,
        password_hash=password_hash,
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_credential

    service = LoginService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="inactive@example.com", password="RealPassword123!")
    with pytest.raises(AuthenticationException) as exc_info:
        await service.login(req)

    # Strictly non-enumerating: identical to unknown email or wrong password
    assert exc_info.value.message == "Invalid email or password"
    repo.update_last_login_at.assert_not_called()


@pytest.mark.asyncio
async def test_login_service_rehashes_when_needed(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="rehash@example.com",
        display_name="Rehash User",
        status=UserStatus.ACTIVE.value,
    )
    raw_password = "ValidPassword123!"
    # Mock password service to simulate needs_rehash = True
    mock_pwd_service = MagicMock(spec=PasswordService)
    mock_pwd_service.verify_password.return_value = PasswordVerificationResult(
        valid=True, needs_rehash=True
    )
    mock_pwd_service.hash_password.return_value = "$argon2id$v=19$m=65536,t=3,p=4$new_hash"

    mock_credential = UserCredential(
        user_id=user_id,
        password_hash="$argon2id$v=19$m=8192,t=1,p=1$old_hash",
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_credential

    service = LoginService(
        session=session,
        repository=repo,
        password_service=mock_pwd_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="rehash@example.com", password=raw_password)
    resp = await service.login(req)

    assert resp.access_token
    assert resp.refresh_token
    mock_pwd_service.hash_password.assert_called_once_with(raw_password)
    repo.update_password_hash.assert_awaited_once_with(
        user_id, "$argon2id$v=19$m=65536,t=3,p=4$new_hash"
    )
    repo.update_last_login_at.assert_awaited_once()
    repo.create_refresh_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_service_maintenance_write_failure_fails_closed(
    fast_password_service: PasswordService,
    token_service: TokenService,
) -> None:
    session = AsyncMock()
    # Mock begin_nested to raise exception during maintenance write
    nested_cm = AsyncMock()
    nested_cm.__aenter__.side_effect = RuntimeError("Database connection dropped")
    session.begin_nested = MagicMock(return_value=nested_cm)

    repo = AsyncMock()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email_normalized="writefail@example.com",
        display_name="Write Fail",
        status=UserStatus.ACTIVE.value,
    )
    raw_password = "ValidPassword123!"
    mock_credential = UserCredential(
        user_id=user_id,
        password_hash=fast_password_service.hash_password(raw_password),
    )
    repo.get_user_by_email.return_value = mock_user
    repo.get_credential_by_user_id.return_value = mock_credential

    service = LoginService(
        session=session,
        repository=repo,
        password_service=fast_password_service,
        account_policy=AccountPolicyService(),
        token_service=token_service,
    )

    req = LoginRequest(email="writefail@example.com", password=raw_password)
    with pytest.raises(RuntimeError, match="Database connection dropped"):
        await service.login(req)

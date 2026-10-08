"""Domain service for user registration and initial account activation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthenticationException
from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.enums import UserStatus
from app.modules.auth.password import PasswordService, run_password_work
from app.modules.auth.refresh import generate_refresh_token, hash_refresh_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.modules.auth.tokens import TokenService


class RegistrationService:
    """Domain service orchestrating user registration and credential creation."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[AuthRepository] = None,
        password_service: Optional[PasswordService] = None,
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)
        self._password_service = password_service or PasswordService()

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Process user registration with strict non-enumerating duplicate handling.

        - Normalizes email (lowercase, stripped).
        - Enforces domain password policy via PasswordService.
        - Hashes password using Argon2id.
        - Atomically creates User (status: ACTIVE) and UserCredential in PostgreSQL.
        - If email already exists or a concurrent registration race occurs, absorbs
          the duplicate silently with dummy verification work and returns the exact
          same generic RegisterResponse without revealing account existence.
        """
        # Canonical email normalization: strip and lowercase only
        email_normalized = request.email.strip().lower()

        # Enforce domain password policy (raises ValidationException if invalid)
        self._password_service.validate_password_policy(request.password)

        # Pre-check for existing identity
        existing_user = await self._repository.get_user_by_email(email_normalized)
        if existing_user is not None:
            # Strictly non-enumerating: perform comparable dummy verification work
            await run_password_work(self._password_service.verify_dummy)
            return RegisterResponse()

        # Hash exact raw password using Argon2id
        password_hash = await run_password_work(self._password_service.hash_password, request.password)

        # Atomic persistence with savepoint protection for concurrent duplicate races
        try:
            async with self._session.begin_nested():
                user = await self._repository.create_user(
                    email_normalized=email_normalized,
                    display_name=request.display_name.strip(),
                    status=UserStatus.ACTIVE,
                )
                await self._repository.create_credential(
                    user_id=user.id,
                    password_hash=password_hash,
                )
        except IntegrityError:
            # Concurrent race condition: another request inserted the same email_normalized.
            # Savepoint was rolled back by begin_nested(), leaving the session valid.
            await run_password_work(self._password_service.verify_dummy)
            return RegisterResponse()

        return RegisterResponse()


class LoginService:
    """Domain service orchestrating user authentication and access token issuance."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[AuthRepository] = None,
        password_service: Optional[PasswordService] = None,
        account_policy: Optional[AccountPolicyService] = None,
        token_service: Optional[TokenService] = None,
        refresh_token_days: Optional[int] = None,
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)
        self._password_service = password_service or PasswordService()
        self._account_policy = account_policy or AccountPolicyService()
        self._token_service = token_service or TokenService()
        self._refresh_token_days = (
            refresh_token_days
            if refresh_token_days is not None
            else get_settings().auth.refresh_token_days
        )

    async def login(self, request: LoginRequest) -> LoginResponse:
        """Authenticate user credentials, issue access token and new refresh token family.

        Enforces strict non-enumeration:
        Any missing user, missing credential, invalid password, or inactive account
        raises AuthenticationException("Invalid email or password").
        Timing mitigation is provided via PasswordService.verify_dummy().
        """
        email_normalized = request.email.strip().lower()

        # Step 1: User lookup
        user = await self._repository.get_user_by_email(email_normalized)
        if user is None:
            await run_password_work(self._password_service.verify_dummy)
            raise AuthenticationException("Invalid email or password")

        # Step 2: Credential lookup
        credential = await self._repository.get_credential_by_user_id(user.id)
        if credential is None:
            await run_password_work(self._password_service.verify_dummy)
            raise AuthenticationException("Invalid email or password")

        # Step 3: Password verification (constant-time native argon2-cffi)
        verify_result = await run_password_work(
            self._password_service.verify_password, request.password, credential.password_hash
        )
        if not verify_result.valid:
            raise AuthenticationException("Invalid email or password")

        # Step 4: Account lifecycle policy (ACTIVE check)
        try:
            self._account_policy.verify_user_can_authenticate(user)
        except AuthenticationException:
            # Non-enumerating: never reveal account status
            raise AuthenticationException("Invalid email or password")

        # Step 5: Maintenance writes and refresh token creation
        # Bounded within savepoint; fail-closed on persistence failure
        now = datetime.now(timezone.utc)
        raw_refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(raw_refresh_token)
        family_id = uuid.uuid4()
        family_expires_at = now + timedelta(days=self._refresh_token_days)

        try:
            async with self._session.begin_nested():
                if verify_result.needs_rehash:
                    new_hash = await run_password_work(self._password_service.hash_password, request.password)
                    await self._repository.update_password_hash(user.id, new_hash)
                await self._repository.update_last_login_at(user.id, now)
                await self._repository.create_refresh_token(
                    user_id=user.id,
                    token_hash=refresh_hash,
                    token_family_id=family_id,
                    expires_at=family_expires_at,
                )
        except Exception:
            # Re-raise to let the database/server error propagate (fail closed)
            raise

        # Step 6: Access token issuance
        token_result = self._token_service.issue_access_token(user.id)

        return LoginResponse(
            access_token=token_result.token,
            token_type="bearer",
            expires_in=token_result.expires_in,
            refresh_token=raw_refresh_token,
            refresh_expires_at=family_expires_at,
        )

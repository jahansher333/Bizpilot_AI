"""Domain service for user registration and initial account activation."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums import UserStatus
from app.modules.auth.password import PasswordService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest, RegisterResponse


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
            self._password_service.verify_dummy()
            return RegisterResponse()

        # Hash exact raw password using Argon2id
        password_hash = self._password_service.hash_password(request.password)

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
            self._password_service.verify_dummy()
            return RegisterResponse()

        return RegisterResponse()

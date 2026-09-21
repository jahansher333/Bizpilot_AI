"""Bounded persistence repository for identity, credentials, and tokens."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums import UserStatus
from app.modules.auth.models import (
    PasswordResetToken,
    RefreshToken,
    User,
    UserCredential,
    generate_uuid,
)


class AuthRepository:
    """Bounded persistence repository for identity and credential storage.

    Compatible with SQLAlchemy 2.x async architecture.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # User Persistence
    # -------------------------------------------------------------------------
    async def create_user(
        self,
        email_normalized: str,
        display_name: str,
        status: UserStatus = UserStatus.ACTIVE,
        user_id: Optional[uuid.UUID] = None,
    ) -> User:
        """Create and persist a new User entity."""
        user = User(
            id=user_id if user_id is not None else generate_uuid(),
            email_normalized=email_normalized,
            display_name=display_name,
            status=status.value if isinstance(status, UserStatus) else status,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a User by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email_normalized: str) -> Optional[User]:
        """Fetch a User by unique normalized email."""
        stmt = select(User).where(User.email_normalized == email_normalized)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Credential Persistence
    # -------------------------------------------------------------------------
    async def create_credential(
        self,
        user_id: uuid.UUID,
        password_hash: str,
        credential_id: Optional[uuid.UUID] = None,
    ) -> UserCredential:
        """Persist a credential hash for a user."""
        credential = UserCredential(
            id=credential_id if credential_id is not None else generate_uuid(),
            user_id=user_id,
            password_hash=password_hash,
        )
        self._session.add(credential)
        await self._session.flush()
        return credential

    async def get_credential_by_user_id(
        self,
        user_id: uuid.UUID,
    ) -> Optional[UserCredential]:
        """Fetch credential by user ID."""
        stmt = select(UserCredential).where(UserCredential.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Refresh Token Persistence
    # -------------------------------------------------------------------------
    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        token_family_id: uuid.UUID,
        expires_at: datetime,
        token_id: Optional[uuid.UUID] = None,
    ) -> RefreshToken:
        """Persist a hashed refresh token."""
        token = RefreshToken(
            id=token_id if token_id is not None else generate_uuid(),
            user_id=user_id,
            token_hash=token_hash,
            token_family_id=token_family_id,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_refresh_token_by_hash(
        self,
        token_hash: str,
    ) -> Optional[RefreshToken]:
        """Fetch a refresh token by unique token hash."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Password Reset Token Persistence
    # -------------------------------------------------------------------------
    async def create_password_reset_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        token_id: Optional[uuid.UUID] = None,
    ) -> PasswordResetToken:
        """Persist a hashed password reset token."""
        token = PasswordResetToken(
            id=token_id if token_id is not None else generate_uuid(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_password_reset_token_by_hash(
        self,
        token_hash: str,
    ) -> Optional[PasswordResetToken]:
        """Fetch a password reset token by unique token hash."""
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

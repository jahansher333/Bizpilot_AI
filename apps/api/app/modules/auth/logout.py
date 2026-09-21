"""Domain service for user logout and session revocation (AUTH-006)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationException
from app.modules.auth.refresh import hash_refresh_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LogoutRequest, LogoutResponse


class LogoutService:
    """Domain service orchestrating current-device logout and logout-all-devices."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[AuthRepository] = None,
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)

    async def logout_current_session(self, request: LogoutRequest) -> LogoutResponse:
        """Terminate the current session family identified by the presented refresh token.

        - Hashes raw refresh token using deterministic SHA-256.
        - Locks the token row under database row-level locking (SELECT ... FOR UPDATE).
        - If token is unknown, raises AuthenticationException (generic non-enumerating 401).
        - If token is already revoked, returns idempotent 200 OK without triggering replay detection.
        - If active, atomically revokes the entire token family.
        - Account state (e.g. disabled) does not prevent revoking a known session family.
        """
        raw_token = request.refresh_token.strip()
        token_hash = hash_refresh_token(raw_token)
        now = datetime.now(timezone.utc)

        token = await self._repository.get_refresh_token_by_hash_for_update(token_hash)
        if token is None:
            raise AuthenticationException("Invalid or expired refresh token")

        # Atomic revocation of the entire session family.
        # Even if the presented token was already rotated during a race, revoking the
        # entire family guarantees that no active descendant survives.
        try:
            async with self._session.begin_nested():
                await self._repository.revoke_token_family(token.token_family_id, now)
        except Exception:
            raise

        return LogoutResponse(
            status="success",
            message="Logged out successfully",
        )

    async def logout_all_sessions(self, user_id: uuid.UUID) -> LogoutResponse:
        """Terminate all active refresh session families for the authenticated user.

        - Revokes all active refresh tokens where user_id == current_user.id and revoked_at IS NULL.
        - Leaves zero surviving refresh sessions for that user across all devices.
        - Repeated calls when 0 active tokens remain succeed idempotently.
        """
        now = datetime.now(timezone.utc)

        try:
            async with self._session.begin_nested():
                # Acquire row-level lock on user entity to serialize against concurrent token rotations
                await self._repository.get_user_by_id_for_update(user_id)
                await self._repository.revoke_all_user_refresh_tokens(user_id, now)
        except Exception:
            raise

        return LogoutResponse(
            status="success",
            message="All sessions logged out successfully",
        )

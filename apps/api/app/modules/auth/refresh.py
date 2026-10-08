"""Refresh token generation, cryptographic hashing, rotation, and replay detection."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationException
from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RefreshRequest, RefreshResponse
from app.modules.auth.tokens import TokenService


def generate_refresh_token() -> str:
    """Generate 32 bytes (256 bits) of CSPRNG entropy encoded as a URL-safe base64 string."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hex digest (64 characters) of raw refresh token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class RefreshService:
    """Domain service managing refresh token rotation, replay detection, and session families."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[AuthRepository] = None,
        account_policy: Optional[AccountPolicyService] = None,
        token_service: Optional[TokenService] = None,
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)
        self._account_policy = account_policy or AccountPolicyService()
        self._token_service = token_service or TokenService()

    async def refresh(self, request: RefreshRequest) -> RefreshResponse:
        """Rotate a valid refresh token, renew access token, and detect token replay.

        - Validates token existence under database row-level locking.
        - Detects replay if token was already revoked, immediately invalidating the entire family.
        - Enforces absolute session lifetime (family expires_at ceiling is preserved).
        - Enforces user account state (rejects disabled/pending users).
        - Atomically revokes presented token and persists single replacement descendant.
        - Returns renewed access token and fresh raw refresh token.
        """
        raw_token = request.refresh_token.strip()
        token_hash = hash_refresh_token(raw_token)
        now = datetime.now(timezone.utc)

        # Lock order is user row, then token row: the same order as logout-all, so a refresh racing
        # a logout-all serializes instead of deadlocking. The unlocked read only finds the owner.
        candidate = await self._repository.get_refresh_token_by_hash(token_hash)
        if candidate is None:
            raise AuthenticationException("Invalid or expired refresh token")
        user = await self._repository.get_user_by_id_for_update(candidate.user_id)

        # Row-level locking protects against concurrent double-spend race conditions
        token = await self._repository.get_refresh_token_by_hash_for_update(token_hash)
        if token is None:
            raise AuthenticationException("Invalid or expired refresh token")

        # Replay detection: if presented token was already consumed/revoked, revoke the ENTIRE family
        if token.revoked_at is not None:
            await self._repository.revoke_token_family(token.token_family_id, now)
            # Commit before raising: the request scope rolls back on errors, which would otherwise
            # undo the family revocation and leave the stolen successor token usable.
            await self._session.commit()
            raise AuthenticationException("Invalid or expired refresh token")

        # Absolute session expiration ceiling check
        if token.expires_at <= now:
            raise AuthenticationException("Invalid or expired refresh token")

        # Verify associated user account state (row locked above)
        if user is None:
            raise AuthenticationException("Invalid or expired refresh token")

        try:
            self._account_policy.verify_user_can_authenticate(user)
        except AuthenticationException:
            # Non-enumerating: never reveal account status
            raise AuthenticationException("Invalid or expired refresh token")

        # Single-use rotation:
        # 1. Mark presented token as consumed/revoked
        # 2. Persist successor token sharing the same token_family_id and exact absolute expires_at
        # 3. Issue fresh access JWT
        await self._repository.revoke_refresh_token(token.id, now)

        new_raw_token = generate_refresh_token()
        new_hash = hash_refresh_token(new_raw_token)

        await self._repository.create_refresh_token(
            user_id=user.id,
            token_hash=new_hash,
            token_family_id=token.token_family_id,
            expires_at=token.expires_at,
        )

        access_token_result = self._token_service.issue_access_token(user.id)

        return RefreshResponse(
            access_token=access_token_result.token,
            token_type="bearer",
            expires_in=access_token_result.expires_in,
            refresh_token=new_raw_token,
            refresh_expires_at=token.expires_at,
        )

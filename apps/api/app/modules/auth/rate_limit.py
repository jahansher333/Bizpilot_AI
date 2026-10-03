"""Database-backed fixed-window rate limiting for credential and recovery endpoints (FIX-003).

Policy (thresholds configurable via AuthenticationSettings):
- login: failed attempts per (email, client IP); a successful login clears the counter.
- forgot-password: requests per email, across all client IPs (limits mail volume to one inbox).
- reset-password: requests per client IP.

Rejections are uniform 429 responses that never reveal whether an account exists.
Subjects are stored only as SHA-256 digests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitException
from app.modules.auth.models import AuthRateLimitBucket

RATE_LIMIT_MESSAGE = "Too many attempts. Please wait a few minutes and try again."


class RateLimitScope(StrEnum):
    LOGIN_FAILURE = "login_failure"
    FORGOT_PASSWORD = "forgot_password"
    RESET_PASSWORD = "reset_password"


def rate_limit_key_hash(scope: RateLimitScope, *parts: str) -> str:
    """Return the SHA-256 digest identifying a rate-limit subject within a scope."""
    material = "\x1f".join([scope.value, *(part.strip().lower() for part in parts)])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthRateLimiter:
    """Fixed-window counters persisted in PostgreSQL; no Redis dependency."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Optional[Settings] = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        cfg = settings or get_settings()
        self._session = session
        self._window = timedelta(minutes=cfg.auth.rate_limit_window_minutes)
        self._login_max_failures = cfg.auth.login_max_failures
        self._recovery_max_requests = cfg.auth.recovery_max_requests
        self._clock = clock

    # Login: count failures only

    async def ensure_login_allowed(self, email: str, client_ip: str) -> None:
        key = rate_limit_key_hash(RateLimitScope.LOGIN_FAILURE, email, client_ip)
        count = await self._current_count(RateLimitScope.LOGIN_FAILURE, key)
        if count >= self._login_max_failures:
            raise RateLimitException(RATE_LIMIT_MESSAGE)

    async def record_login_failure(self, email: str, client_ip: str) -> None:
        key = rate_limit_key_hash(RateLimitScope.LOGIN_FAILURE, email, client_ip)
        await self._hit(RateLimitScope.LOGIN_FAILURE, key)

    async def clear_login_failures(self, email: str, client_ip: str) -> None:
        key = rate_limit_key_hash(RateLimitScope.LOGIN_FAILURE, email, client_ip)
        await self._session.execute(
            delete(AuthRateLimitBucket).where(
                AuthRateLimitBucket.scope == RateLimitScope.LOGIN_FAILURE.value,
                AuthRateLimitBucket.key_hash == key,
            )
        )

    # Recovery: count every request

    async def consume_forgot_password(self, email: str) -> bool:
        """Record a forgot-password request; return False when the limit is exceeded."""
        key = rate_limit_key_hash(RateLimitScope.FORGOT_PASSWORD, email)
        count = await self._hit(RateLimitScope.FORGOT_PASSWORD, key)
        return count <= self._recovery_max_requests

    async def consume_reset_password(self, client_ip: str) -> bool:
        """Record a reset-password request; return False when the limit is exceeded."""
        key = rate_limit_key_hash(RateLimitScope.RESET_PASSWORD, client_ip)
        count = await self._hit(RateLimitScope.RESET_PASSWORD, key)
        return count <= self._recovery_max_requests

    # Internals

    async def _current_count(self, scope: RateLimitScope, key_hash: str) -> int:
        row = (
            await self._session.execute(
                select(AuthRateLimitBucket.attempt_count, AuthRateLimitBucket.window_started_at).where(
                    AuthRateLimitBucket.scope == scope.value,
                    AuthRateLimitBucket.key_hash == key_hash,
                )
            )
        ).first()
        if row is None or row.window_started_at <= self._clock() - self._window:
            return 0
        return row.attempt_count

    async def _hit(self, scope: RateLimitScope, key_hash: str) -> int:
        """Atomically increment the counter, restarting it when the window has elapsed."""
        now = self._clock()
        window_expired = AuthRateLimitBucket.window_started_at <= now - self._window
        stmt = (
            pg_insert(AuthRateLimitBucket)
            .values(
                scope=scope.value,
                key_hash=key_hash,
                window_started_at=now,
                attempt_count=1,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AuthRateLimitBucket.scope, AuthRateLimitBucket.key_hash],
                set_={
                    "attempt_count": case(
                        (window_expired, 1),
                        else_=AuthRateLimitBucket.attempt_count + 1,
                    ),
                    "window_started_at": case(
                        (window_expired, now),
                        else_=AuthRateLimitBucket.window_started_at,
                    ),
                    "updated_at": now,
                },
            )
            .returning(AuthRateLimitBucket.attempt_count)
        )
        return (await self._session.execute(stmt)).scalar_one()

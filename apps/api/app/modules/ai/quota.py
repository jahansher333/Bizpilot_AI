"""Daily assistant request allowance per organization (SEC-P1 F4).

Each assistant request is counted against the organization's allowance for its local calendar day
(organization timezone), so the allowance resets at the business's midnight. Requests over the
allowance are refused before any provider call, which bounds AI cost and abuse.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.ai.models import AIDailyUsage
from app.modules.dashboard.timezone import get_zone_info

AI_DAILY_LIMIT_MESSAGE = (
    "Your business has reached today's BizPilot Assistant limit. It resets at midnight."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIDailyQuota:
    """Atomic per-organization daily request counter persisted in PostgreSQL."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Optional[Settings] = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        cfg = settings or get_settings()
        self._session = session
        self._limit = cfg.ai.daily_requests_per_organization
        self._clock = clock

    def local_date(self, timezone_name: str | None) -> date:
        return self._clock().astimezone(get_zone_info(timezone_name)).date()

    async def consume(self, organization_id: uuid.UUID, timezone_name: str | None) -> bool:
        """Count one request for today; return False when the allowance is exceeded."""
        now = self._clock()
        stmt = (
            pg_insert(AIDailyUsage)
            .values(
                organization_id=organization_id,
                usage_date=self.local_date(timezone_name),
                request_count=1,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AIDailyUsage.organization_id, AIDailyUsage.usage_date],
                set_={"request_count": AIDailyUsage.request_count + 1, "updated_at": now},
            )
            .returning(AIDailyUsage.request_count)
        )
        count = (await self._session.execute(stmt)).scalar_one()
        return count <= self._limit

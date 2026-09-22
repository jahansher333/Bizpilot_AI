"""Scoped append-only repository for internal trace events (ORG-006)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.trace.models import InternalTraceEvent


class InternalTraceRepository(ScopedRepository[InternalTraceEvent]):
    """Tenant-scoped append-only repository for internal trace events.

    Bound at construction to an AsyncSession and trusted organization_id.
    Exposes only append-oriented and read operations.
    Exposes NO update, delete, bulk_update, or bulk_delete APIs.
    """

    model_cls = InternalTraceEvent

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        super().__init__(
            session=session,
            organization_id=organization_id,
            model_cls=InternalTraceEvent,
        )

    def add_event(self, event: InternalTraceEvent) -> InternalTraceEvent:
        """Add a newly created trace event to the database session.

        Enforces that the event's organization_id strictly matches the repository's
        bound organization_id before staging.
        """
        if event.organization_id != self._organization_id:
            raise ValueError(
                f"Event organization_id {event.organization_id} does not match "
                f"repository organization_id {self._organization_id}"
            )
        self._session.add(event)
        return event

    async def get_event_by_id(self, event_id: uuid.UUID) -> Optional[InternalTraceEvent]:
        """Fetch a trace event by ID within the bound organization scope."""
        return await self.get_by_id(event_id)

    async def list_events(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Sequence[InternalTraceEvent]:
        """List trace events for the bound organization, ordered by created_at DESC."""
        return await self.list_scoped(
            order_by=InternalTraceEvent.created_at.desc(),
            limit=limit,
            offset=offset,
        )

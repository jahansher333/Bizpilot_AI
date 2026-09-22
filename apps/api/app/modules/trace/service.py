"""Service layer for recording sanitized internal trace events (ORG-006)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationException
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.models import InternalTraceEvent
from app.modules.trace.repository import InternalTraceRepository
from app.modules.trace.sanitizer import sanitize_and_validate_metadata


class InternalTraceService:
    """Internal service for recording bounded operational and security trace events.

    Bound at construction to an AsyncSession and trusted organization_id.
    NEVER calls commit() or rollback(); caller owns the transaction boundary.
    """

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> None:
        if not isinstance(organization_id, uuid.UUID):
            raise TypeError("organization_id must be a valid UUID instance")
        self._session = session
        self._organization_id = organization_id
        self._repo = InternalTraceRepository(session=session, organization_id=organization_id)

    @property
    def organization_id(self) -> uuid.UUID:
        """Trusted tenant ID."""
        return self._organization_id

    @property
    def session(self) -> AsyncSession:
        """Active database session."""
        return self._session

    @property
    def repository(self) -> InternalTraceRepository:
        """Underlying scoped repository."""
        return self._repo

    async def record_event(
        self,
        *,
        action: str | TraceAction,
        outcome: str | TraceOutcome,
        actor_user_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        request_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> InternalTraceEvent:
        """Sanitize metadata, validate inputs, and persist an append-only trace event.

        Performs:
        1. Action validation (non-empty, >= 3 characters, <= 64 characters)
        2. Outcome validation (must match approved TraceOutcome)
        3. Metadata recursive sanitization & 4096-byte limit enforcement
        4. Model instantiation bound to trusted self._organization_id
        5. Repository staging and session.flush()
        """
        # 1. Action validation
        action_val = action.value if isinstance(action, TraceAction) else str(action)
        action_clean = action_val.strip() if action_val else ""
        if len(action_clean) < 3:
            raise ValidationException("Trace action must be at least 3 characters")
        if len(action_clean) > 64:
            raise ValidationException("Trace action must not exceed 64 characters")

        # 2. Outcome validation
        outcome_val = outcome.value if isinstance(outcome, TraceOutcome) else str(outcome)
        valid_outcomes = {o.value for o in TraceOutcome}
        if outcome_val not in valid_outcomes:
            raise ValidationException(
                f"Invalid trace outcome: '{outcome_val}'. Must be one of: {sorted(valid_outcomes)}"
            )

        # 3. Actor user ID validation
        if actor_user_id is not None and not isinstance(actor_user_id, uuid.UUID):
            raise TypeError("actor_user_id must be a UUID or None")

        # 4. Target ID validation
        if target_id is not None and not isinstance(target_id, uuid.UUID):
            raise TypeError("target_id must be a UUID or None")

        # 5. Sanitize and validate metadata (enforces <= 4096 bytes UTF-8)
        sanitized_metadata = sanitize_and_validate_metadata(metadata)

        # 6. Normalize request_id
        normalized_request_id = request_id.strip() if request_id and request_id.strip() else None

        # 7. Create model bound to trusted organization
        event = InternalTraceEvent(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            actor_user_id=actor_user_id,
            action=action_clean,
            target_type=target_type.strip() if target_type and target_type.strip() else None,
            target_id=target_id,
            outcome=outcome_val,
            request_id=normalized_request_id,
            event_metadata=sanitized_metadata,
        )

        # 8. Stage in repository and flush to DB within caller's transaction
        self._repo.add_event(event)
        await self._session.flush()

        return event

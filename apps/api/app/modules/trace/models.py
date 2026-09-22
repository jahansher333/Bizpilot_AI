"""SQLAlchemy model for internal operational and security trace events (ORG-006)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InternalTraceEvent(Base):
    """Immutable, append-only record of a security or correctness event within a tenant.

    Satisfies the TenantScopedModel protocol (exposes `id` and `organization_id`).
    """

    __tablename__ = "internal_trace_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_internal_trace_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_internal_trace_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    target_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    # Note: 'metadata' is reserved on Base for MetaData, so mapped attribute is event_metadata
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'denied', 'failed')",
            name="outcome",
        ),
        CheckConstraint(
            "char_length(trim(action)) >= 3",
            name="action_len",
        ),
        Index("ix_internal_trace_events_organization_id", "organization_id"),
        Index("ix_internal_trace_events_org_created", "organization_id", "created_at"),
        Index("ix_internal_trace_events_request_id", "request_id"),
    )

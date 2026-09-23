"""SQLAlchemy model for idempotency keys (ORG-006 / write-slice adoption)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    """Tenant-scoped idempotency record for retry-sensitive write operations."""

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_idempotency_keys_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_idempotency_keys_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'completed'"),
        default="completed",
    )
    response_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    response_payload: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_keys_org_user_op_key",
        ),
        Index(
            "ix_idempotency_keys_lookup",
            "organization_id",
            "user_id",
            "operation",
            "idempotency_key",
        ),
    )

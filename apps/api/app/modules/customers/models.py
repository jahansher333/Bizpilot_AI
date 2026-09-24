"""SQLAlchemy model for tenant-scoped customers (CUS-001)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    """Tenant-scoped customer entity.

    Satisfies the TenantScopedModel protocol (exposes `id` and `organization_id`).
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_customers_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        default="active",
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_customers_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="check_customers_status",
        ),
        CheckConstraint(
            "char_length(trim(name)) >= 1",
            name="check_customers_name_len",
        ),
        CheckConstraint(
            "phone IS NULL OR char_length(trim(phone)) >= 3",
            name="check_customers_phone_len",
        ),
        Index("ix_customers_organization_id", "organization_id"),
        Index("ix_customers_org_status", "organization_id", "status"),
        Index("ix_customers_org_name", "organization_id", "name"),
        Index(
            "uq_customers_org_active_phone",
            "organization_id",
            "phone",
            unique=True,
            postgresql_where=text("status = 'active' AND phone IS NOT NULL"),
        ),
    )

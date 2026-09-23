"""SQLAlchemy model for tenant-scoped products (CAT-002)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    """Tenant-scoped product entity.

    Satisfies the TenantScopedModel protocol (exposes `id` and `organization_id`).
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_products_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "categories.id",
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    base_unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'piece'"),
        default="piece",
    )
    default_price_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
        default="PKR",
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
            name="fk_products_created_by_user_id_users",
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
            name="status",
        ),
        CheckConstraint(
            "default_price_minor >= 0",
            name="price_non_negative",
        ),
        CheckConstraint(
            "char_length(trim(code)) >= 1",
            name="code_len",
        ),
        CheckConstraint(
            "char_length(trim(name)) >= 2",
            name="name_len",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="currency_len",
        ),
        CheckConstraint(
            "char_length(trim(base_unit)) >= 1",
            name="base_unit_len",
        ),
        Index("ix_products_organization_id", "organization_id"),
        Index("ix_products_org_status", "organization_id", "status"),
        Index("ix_products_org_category", "organization_id", "category_id"),
        Index(
            "uq_products_org_active_code",
            "organization_id",
            text("lower(trim(code))"),
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

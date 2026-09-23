"""SQLAlchemy models for tenant-scoped inventory balances and movements (INV-001)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryBalance(Base):
    """Tenant-scoped current inventory balance for a product.

    Satisfies the TenantScopedModel protocol (exposes `id` and `organization_id`).
    Every product has at most one balance record per organization.
    `on_hand_quantity` must remain non-negative.
    """

    __tablename__ = "inventory_balances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_inventory_balances_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_inventory_balances_product_id_products",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    on_hand_quantity: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            name="product_id",
        ),
        UniqueConstraint(
            "organization_id",
            "product_id",
            name="org_product",
        ),
        CheckConstraint(
            "on_hand_quantity >= 0",
            name="quantity_non_negative",
        ),
        Index(
            "ix_inventory_balances_org_product",
            "organization_id",
            "product_id",
        ),
    )


class InventoryMovement(Base):
    """Append-only tenant-scoped inventory movement explaining stock changes.

    Satisfies the TenantScopedModel protocol (exposes `id` and `organization_id`).
    `quantity_delta` represents change (+/-) and must be non-zero.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_inventory_movements_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_inventory_movements_product_id_products",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    quantity_delta: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_inventory_movements_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "quantity_delta != 0",
            name="quantity_non_zero",
        ),
        CheckConstraint(
            "movement_type IN ('opening', 'sale', 'adjustment', 'correction', 'void_reversal')",
            name="movement_type_valid",
        ),
        Index(
            "ix_inventory_movements_org_product_created",
            "organization_id",
            "product_id",
            "created_at",
        ),
        Index(
            "ix_inventory_movements_org_type_created",
            "organization_id",
            "movement_type",
            "created_at",
        ),
    )

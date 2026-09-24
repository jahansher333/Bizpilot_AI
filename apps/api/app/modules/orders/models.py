"""SQLAlchemy models for tenant-scoped orders and order items (ORD-001)."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Order(Base):
    """Tenant-scoped sale/order entity.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_orders_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    order_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            name="fk_orders_customer_id_customers",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        default="active",
    )
    order_total_minor: Mapped[int] = mapped_column(
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
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_orders_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    corrects_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_orders_corrects_order_id_orders",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    replaced_by_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_orders_replaced_by_order_id_orders",
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
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    items: Mapped[list[OrderItem]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'voided', 'corrected')",
            name="check_orders_status",
        ),
        CheckConstraint(
            "order_total_minor >= 0",
            name="check_orders_total_non_negative",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_orders_currency_len",
        ),
        CheckConstraint(
            "char_length(trim(order_number)) >= 1",
            name="check_orders_number_len",
        ),
        UniqueConstraint(
            "organization_id",
            "order_number",
            name="uq_orders_org_order_number",
        ),
        Index("ix_orders_organization_id", "organization_id"),
        Index("ix_orders_org_customer_ordered", "organization_id", "customer_id", "ordered_at"),
        Index("ix_orders_org_ordered_at", "organization_id", "ordered_at"),
        Index("ix_orders_org_status", "organization_id", "status"),
    )


class OrderItem(Base):
    """Immutable line-item snapshot of a product sold in an order.

    Preserves product_name_snapshot, product_code_snapshot, and unit_snapshot
    even if the product is later modified or archived.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_order_items_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_order_items_order_id_orders",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "products.id",
            name="fk_order_items_product_id_products",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    product_name_snapshot: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    product_code_snapshot: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    unit_snapshot: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    unit_price_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    line_total_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
        default="PKR",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    order: Mapped[Order] = relationship("Order", back_populates="items")

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="check_order_items_quantity_positive",
        ),
        CheckConstraint(
            "unit_price_minor >= 0",
            name="check_order_items_unit_price_non_negative",
        ),
        CheckConstraint(
            "line_total_minor >= 0",
            name="check_order_items_line_total_non_negative",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_order_items_currency_len",
        ),
        CheckConstraint(
            "line_total_minor = quantity * unit_price_minor",
            name="check_order_items_line_total_calc",
        ),
        Index("ix_order_items_organization_id", "organization_id"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
    )

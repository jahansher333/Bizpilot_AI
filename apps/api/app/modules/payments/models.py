"""SQLAlchemy models for tenant-scoped payments (PAY-001)."""

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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Payment(Base):
    """Tenant-scoped recorded business payment receipt.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    Optionally associated with a single customer and/or a single order.
    P0 recording only; does not claim bank settlement or reconciliation.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_payments_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
            name="fk_payments_customer_id_customers",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            name="fk_payments_order_id_orders",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    amount_minor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
        default="PKR",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    account_label: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    external_reference: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
        default="active",
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_payments_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    corrects_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            name="fk_payments_corrects_payment_id_payments",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    replaced_by_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            name="fk_payments_replaced_by_payment_id_payments",
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

    organization = relationship("Organization")
    customer = relationship("Customer")
    order = relationship("Order")
    created_by = relationship("User")
    corrects_payment = relationship("Payment", remote_side=[id], foreign_keys=[corrects_payment_id])
    replaced_by_payment = relationship("Payment", remote_side=[id], foreign_keys=[replaced_by_payment_id])

    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="check_payments_amount_positive",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_payments_currency_len",
        ),
        CheckConstraint(
            "status IN ('active', 'voided', 'corrected')",
            name="check_payments_status",
        ),
        CheckConstraint(
            "channel IN ('cash', 'bank_transfer', 'digital', 'other')",
            name="check_payments_channel",
        ),
        Index("ix_payments_organization_id", "organization_id"),
        Index("ix_payments_org_received_at", "organization_id", "received_at"),
        Index("ix_payments_org_customer_received", "organization_id", "customer_id", "received_at"),
        Index("ix_payments_org_order_id", "organization_id", "order_id"),
        Index("ix_payments_org_status", "organization_id", "status"),
        Index("ix_payments_org_ext_ref", "organization_id", "external_reference"),
    )

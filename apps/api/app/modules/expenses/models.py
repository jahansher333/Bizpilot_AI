"""SQLAlchemy models for tenant-scoped expenses and categories (EXP-001)."""

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


class ExpenseCategory(Base):
    """Lightweight tenant-scoped expense category for operational grouping.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    """

    __tablename__ = "expense_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_expense_categories_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
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
        onupdate=datetime.now,
    )

    # Relationships
    expenses: Mapped[list[Expense]] = relationship(
        "Expense",
        back_populates="category",
        foreign_keys="Expense.expense_category_id",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="check_expense_categories_status",
        ),
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="check_expense_categories_name_nonempty",
        ),
        Index("ix_expense_categories_organization_id", "organization_id"),
        Index("ix_expense_categories_org_status", "organization_id", "status"),
        Index(
            "uq_expense_categories_org_active_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class Expense(Base):
    """Tenant-scoped recorded operational expense.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    Optionally classified by an ExpenseCategory belonging to the same organization.
    P0 recording only; no full general ledger, journal entries, or payroll.
    """

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_expenses_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    expense_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "expense_categories.id",
            name="fk_expenses_expense_category_id_expense_categories",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'PKR'"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    payment_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'cash'"),
    )
    payee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_expenses_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    corrects_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "expenses.id",
            name="fk_expenses_corrects_expense_id_expenses",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    replaced_by_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "expenses.id",
            name="fk_expenses_replaced_by_expense_id_expenses",
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
        onupdate=datetime.now,
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    category: Mapped[ExpenseCategory | None] = relationship(
        "ExpenseCategory",
        back_populates="expenses",
        foreign_keys=[expense_category_id],
    )
    corrects_expense: Mapped[Expense | None] = relationship(
        "Expense",
        remote_side=[id],
        foreign_keys=[corrects_expense_id],
        post_update=True,
    )
    replaced_by_expense: Mapped[Expense | None] = relationship(
        "Expense",
        remote_side=[id],
        foreign_keys=[replaced_by_expense_id],
        post_update=True,
    )

    __table_args__ = (
        CheckConstraint(
            "amount_minor > 0",
            name="check_expenses_amount_positive",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_expenses_currency_len",
        ),
        CheckConstraint(
            "status IN ('active', 'voided', 'corrected')",
            name="check_expenses_status",
        ),
        CheckConstraint(
            "payment_method IN ('cash', 'bank_transfer', 'cheque', 'mobile_wallet', 'digital', 'other')",
            name="check_expenses_payment_method",
        ),
        Index("ix_expenses_organization_id", "organization_id"),
        Index("ix_expenses_org_occurred_at", "organization_id", "occurred_at"),
        Index("ix_expenses_org_status", "organization_id", "status"),
        Index("ix_expenses_category_id", "organization_id", "expense_category_id"),
    )

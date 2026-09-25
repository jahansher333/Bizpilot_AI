"""Expense categories and expenses persistence schema (EXP-001).

Revision ID: 0012_expenses
Revises: 0011_payments
Create Date: 2026-09-26 01:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012_expenses"
down_revision: Union[str, None] = "0011_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expense Categories Table
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_expense_categories_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="check_expense_categories_status",
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0",
            name="check_expense_categories_name_nonempty",
        ),
    )

    op.create_index(
        "ix_expense_categories_organization_id",
        "expense_categories",
        ["organization_id"],
    )
    op.create_index(
        "ix_expense_categories_org_status",
        "expense_categories",
        ["organization_id", "status"],
    )
    # Unique active category name per organization
    op.create_index(
        "uq_expense_categories_org_active_name",
        "expense_categories",
        ["organization_id", "name"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # 2. Expenses Table
    op.create_table(
        "expenses",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_expenses_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "expense_category_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "expense_categories.id",
                name="fk_expenses_expense_category_id_expense_categories",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(32), server_default=sa.text("'cash'"), nullable=False),
        sa.Column("payee", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_expenses_created_by_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "corrects_expense_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "expenses.id",
                name="fk_expenses_corrects_expense_id_expenses",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "replaced_by_expense_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "expenses.id",
                name="fk_expenses_replaced_by_expense_id_expenses",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "amount_minor > 0",
            name="check_expenses_amount_positive",
        ),
        sa.CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_expenses_currency_len",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'voided', 'corrected')",
            name="check_expenses_status",
        ),
        sa.CheckConstraint(
            "payment_method IN ('cash', 'bank_transfer', 'cheque', 'mobile_wallet', 'digital', 'other')",
            name="check_expenses_payment_method",
        ),
    )

    op.create_index(
        "ix_expenses_organization_id",
        "expenses",
        ["organization_id"],
    )
    op.create_index(
        "ix_expenses_org_occurred_at",
        "expenses",
        ["organization_id", "occurred_at"],
    )
    op.create_index(
        "ix_expenses_org_status",
        "expenses",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_expenses_category_id",
        "expenses",
        ["organization_id", "expense_category_id"],
    )

    # 3. Cross-tenant consistency trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_check_expenses_tenant_consistency()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.expense_category_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM expense_categories
                    WHERE id = NEW.expense_category_id
                      AND organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'Cross-tenant violation: expense_category does not belong to organization %', NEW.organization_id
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_expenses_tenant_consistency
        BEFORE INSERT OR UPDATE ON expenses
        FOR EACH ROW
        EXECUTE FUNCTION fn_check_expenses_tenant_consistency();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_expenses_tenant_consistency ON expenses;")
    op.execute("DROP FUNCTION IF EXISTS fn_check_expenses_tenant_consistency();")
    op.drop_table("expenses")
    op.drop_table("expense_categories")

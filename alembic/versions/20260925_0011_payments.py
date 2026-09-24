"""Payment persistence schema (PAY-001).

Revision ID: 0011_payments
Revises: 0010_orders
Create Date: 2026-09-25 03:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_payments"
down_revision: Union[str, None] = "0010_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_payments_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "customers.id",
                name="fk_payments_customer_id_customers",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_payments_order_id_orders",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("account_label", sa.String(128), nullable=True),
        sa.Column("external_reference", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_payments_created_by_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "corrects_payment_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "payments.id",
                name="fk_payments_corrects_payment_id_payments",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "replaced_by_payment_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "payments.id",
                name="fk_payments_replaced_by_payment_id_payments",
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
            name="check_payments_amount_positive",
        ),
        sa.CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_payments_currency_len",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'voided', 'corrected')",
            name="check_payments_status",
        ),
        sa.CheckConstraint(
            "channel IN ('cash', 'bank_transfer', 'digital', 'other')",
            name="check_payments_channel",
        ),
    )

    op.create_index(
        "ix_payments_organization_id",
        "payments",
        ["organization_id"],
    )
    op.create_index(
        "ix_payments_org_received_at",
        "payments",
        ["organization_id", "received_at"],
    )
    op.create_index(
        "ix_payments_org_customer_received",
        "payments",
        ["organization_id", "customer_id", "received_at"],
    )
    op.create_index(
        "ix_payments_org_order_id",
        "payments",
        ["organization_id", "order_id"],
    )
    op.create_index(
        "ix_payments_org_status",
        "payments",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_payments_org_ext_ref",
        "payments",
        ["organization_id", "external_reference"],
    )

    # Database-level cross-tenant relationship integrity trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_payments_tenant_consistency()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.order_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM orders
                    WHERE id = NEW.order_id AND organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'Cross-organization reference: order does not belong to payment organization'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF NEW.customer_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM customers
                    WHERE id = NEW.customer_id AND organization_id = NEW.organization_id
                ) THEN
                    RAISE EXCEPTION 'Cross-organization reference: customer does not belong to payment organization'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_payments_tenant_consistency
        BEFORE INSERT OR UPDATE ON payments
        FOR EACH ROW
        EXECUTE FUNCTION check_payments_tenant_consistency();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_payments_tenant_consistency ON payments;")
    op.execute("DROP FUNCTION IF EXISTS check_payments_tenant_consistency();")

    op.drop_index("ix_payments_org_ext_ref", table_name="payments")
    op.drop_index("ix_payments_org_status", table_name="payments")
    op.drop_index("ix_payments_org_order_id", table_name="payments")
    op.drop_index("ix_payments_org_customer_received", table_name="payments")
    op.drop_index("ix_payments_org_received_at", table_name="payments")
    op.drop_index("ix_payments_organization_id", table_name="payments")
    op.drop_table("payments")

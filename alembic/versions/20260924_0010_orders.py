"""Order and order-item persistence schema (ORD-001).

Revision ID: 0010_orders
Revises: 0009_customers
Create Date: 2026-09-24 21:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_orders"
down_revision: Union[str, None] = "0009_customers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_orders_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "customers.id",
                name="fk_orders_customer_id_customers",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "ordered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("order_total_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_orders_created_by_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "corrects_order_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_orders_corrects_order_id_orders",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "replaced_by_order_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_orders_replaced_by_order_id_orders",
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
            "status IN ('active', 'voided', 'corrected')",
            name="check_orders_status",
        ),
        sa.CheckConstraint(
            "order_total_minor >= 0",
            name="check_orders_total_non_negative",
        ),
        sa.CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_orders_currency_len",
        ),
        sa.CheckConstraint(
            "char_length(trim(order_number)) >= 1",
            name="check_orders_number_len",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "order_number",
            name="uq_orders_org_order_number",
        ),
    )

    op.create_index(
        "ix_orders_organization_id",
        "orders",
        ["organization_id"],
    )
    op.create_index(
        "ix_orders_org_customer_ordered",
        "orders",
        ["organization_id", "customer_id", "ordered_at"],
    )
    op.create_index(
        "ix_orders_org_ordered_at",
        "orders",
        ["organization_id", "ordered_at"],
    )
    op.create_index(
        "ix_orders_org_status",
        "orders",
        ["organization_id", "status"],
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_order_items_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_order_items_order_id_orders",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                name="fk_order_items_product_id_products",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column("product_name_snapshot", sa.String(255), nullable=False),
        sa.Column("product_code_snapshot", sa.String(64), nullable=False),
        sa.Column("unit_snapshot", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="check_order_items_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price_minor >= 0",
            name="check_order_items_unit_price_non_negative",
        ),
        sa.CheckConstraint(
            "line_total_minor >= 0",
            name="check_order_items_line_total_non_negative",
        ),
        sa.CheckConstraint(
            "char_length(currency_code) = 3",
            name="check_order_items_currency_len",
        ),
        sa.CheckConstraint(
            "line_total_minor = quantity * unit_price_minor",
            name="check_order_items_line_total_calc",
        ),
    )

    op.create_index(
        "ix_order_items_organization_id",
        "order_items",
        ["organization_id"],
    )
    op.create_index(
        "ix_order_items_order_id",
        "order_items",
        ["order_id"],
    )
    op.create_index(
        "ix_order_items_product_id",
        "order_items",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_items_product_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_index("ix_order_items_organization_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_org_status", table_name="orders")
    op.drop_index("ix_orders_org_ordered_at", table_name="orders")
    op.drop_index("ix_orders_org_customer_ordered", table_name="orders")
    op.drop_index("ix_orders_organization_id", table_name="orders")
    op.drop_table("orders")

"""Inventory balances and movements persistence schema.

Revision ID: 0007_inventory
Revises: 0006_products
Create Date: 2026-09-24 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_inventory"
down_revision: Union[str, None] = "0006_products"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. inventory_balances table
    op.create_table(
        "inventory_balances",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "on_hand_quantity",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "on_hand_quantity >= 0",
            name="quantity_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_inventory_balances_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_inventory_balances_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_balances"),
        sa.UniqueConstraint("product_id", name="product_id"),
        sa.UniqueConstraint("organization_id", "product_id", name="org_product"),
    )
    op.create_index(
        "ix_inventory_balances_org_product",
        "inventory_balances",
        ["organization_id", "product_id"],
        unique=False,
    )

    # 2. inventory_movements table
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity_delta", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity_delta != 0",
            name="quantity_non_zero",
        ),
        sa.CheckConstraint(
            "movement_type IN ('opening', 'sale', 'adjustment', 'correction', 'void_reversal')",
            name="movement_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_inventory_movements_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_inventory_movements_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_inventory_movements_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_movements"),
    )
    op.create_index(
        "ix_inventory_movements_org_product_created",
        "inventory_movements",
        ["organization_id", "product_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_org_type_created",
        "inventory_movements",
        ["organization_id", "movement_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_org_type_created", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_org_product_created", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_inventory_balances_org_product", table_name="inventory_balances")
    op.drop_table("inventory_balances")

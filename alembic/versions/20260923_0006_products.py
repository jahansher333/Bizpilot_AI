"""Products persistence schema.

Revision ID: 0006_products
Revises: 0005_categories
Create Date: 2026-09-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_products"
down_revision: Union[str, None] = "0005_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_unit", sa.String(length=32), server_default=sa.text("'piece'"), nullable=False),
        sa.Column("default_price_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("currency_code", sa.String(length=3), server_default=sa.text("'PKR'"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=True), nullable=True),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="status",
        ),
        sa.CheckConstraint(
            "default_price_minor >= 0",
            name="price_non_negative",
        ),
        sa.CheckConstraint(
            "char_length(trim(code)) >= 1",
            name="code_len",
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) >= 2",
            name="name_len",
        ),
        sa.CheckConstraint(
            "char_length(currency_code) = 3",
            name="currency_len",
        ),
        sa.CheckConstraint(
            "char_length(trim(base_unit)) >= 1",
            name="base_unit_len",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_products_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_products_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
    )
    op.create_index(
        "ix_products_organization_id",
        "products",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_products_org_status",
        "products",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_products_org_category",
        "products",
        ["organization_id", "category_id"],
        unique=False,
    )
    op.create_index(
        "uq_products_org_active_code",
        "products",
        ["organization_id", sa.text("lower(trim(code))")],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_products_org_active_code", table_name="products")
    op.drop_index("ix_products_org_category", table_name="products")
    op.drop_index("ix_products_org_status", table_name="products")
    op.drop_index("ix_products_organization_id", table_name="products")
    op.drop_table("products")

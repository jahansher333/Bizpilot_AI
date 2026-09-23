"""Categories persistence schema.

Revision ID: 0005_categories
Revises: 0004_internal_trace_events
Create Date: 2026-09-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_categories"
down_revision: Union[str, None] = "0004_internal_trace_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
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
            "char_length(trim(name)) >= 2",
            name="name_len",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_categories_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_categories_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
    )
    op.create_index(
        "ix_categories_organization_id",
        "categories",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_categories_org_status",
        "categories",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_categories_org_active_name",
        "categories",
        ["organization_id", sa.text("lower(trim(name))")],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_categories_org_active_name", table_name="categories")
    op.drop_index("ix_categories_org_status", table_name="categories")
    op.drop_index("ix_categories_organization_id", table_name="categories")
    op.drop_table("categories")

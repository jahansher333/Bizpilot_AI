"""Customer persistence schema (CUS-001).

Revision ID: 0009_customers
Revises: 0008_idempotency_keys
Create Date: 2026-09-24 20:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_customers"
down_revision: Union[str, None] = "0008_idempotency_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_customers_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_customers_created_by_user_id_users",
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="check_customers_status",
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) >= 1",
            name="check_customers_name_len",
        ),
        sa.CheckConstraint(
            "phone IS NULL OR char_length(trim(phone)) >= 3",
            name="check_customers_phone_len",
        ),
    )

    op.create_index(
        "ix_customers_organization_id",
        "customers",
        ["organization_id"],
    )
    op.create_index(
        "ix_customers_org_status",
        "customers",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_customers_org_name",
        "customers",
        ["organization_id", "name"],
    )
    op.create_index(
        "uq_customers_org_active_phone",
        "customers",
        ["organization_id", "phone"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND phone IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_customers_org_active_phone", table_name="customers")
    op.drop_index("ix_customers_org_name", table_name="customers")
    op.drop_index("ix_customers_org_status", table_name="customers")
    op.drop_index("ix_customers_organization_id", table_name="customers")
    op.drop_table("customers")

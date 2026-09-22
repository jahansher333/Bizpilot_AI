"""Organizations and initial membership schema.

Revision ID: 0003_organizations_and_members
Revises: 0002_auth_identity_credentials
Create Date: 2026-09-22 05:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_organizations_and_members"
down_revision: Union[str, None] = "0002_auth_identity_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("currency_code", sa.String(length=3), server_default="PKR", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Karachi", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(trim(display_name)) >= 2", name="ck_organizations_display_name_len"),
        sa.CheckConstraint("char_length(currency_code) = 3", name="ck_organizations_currency_code_len"),
        sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name="ck_organizations_status"),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )

    # 2. organization_members table
    # Restrictive foreign key delete semantics per Founder Decision Option A
    op.create_table(
        "organization_members",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("invited_by_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'manager', 'staff')", name="ck_organization_members_role"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'invited')", name="ck_organization_members_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_organization_members_organization_id_organizations"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_organization_members_user_id_users"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], name="fk_organization_members_invited_by_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_organization_members"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"], unique=False)
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_organization_members_organization_id", table_name="organization_members")
    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_table("organizations")

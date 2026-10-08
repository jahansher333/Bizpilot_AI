"""Email-addressed organization invitations (SEC-P1 F5).

Revision ID: 0016_org_invitations
Revises: 0015_ai_daily_usage
Create Date: 2026-10-09 00:00:00.000000+00:00

Invitations used to be organization_members rows with status 'invited', which required an existing
account and let the invite form reveal which emails were registered. They now live in their own
table keyed by email. Existing pending invitations are moved over (their member rows never became
memberships) and removed from organization_members; they get a fresh 7-day expiry.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0016_org_invitations"
down_revision: Union[str, None] = "0015_ai_daily_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("email_normalized", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("invited_by_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'manager', 'staff')", name="ck_organization_invitations_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')", name="ck_organization_invitations_status"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_organization_invitations_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"],
            name="fk_organization_invitations_invited_by_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"], ["users.id"],
            name="fk_organization_invitations_accepted_by_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invitations"),
    )
    op.create_index(
        "ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"]
    )
    op.create_index(
        "ix_organization_invitations_email_normalized", "organization_invitations", ["email_normalized"]
    )
    op.create_index(
        "uq_organization_invitations_org_pending_email",
        "organization_invitations",
        ["organization_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Move pending invitations; the invitation keeps the old member row's id and timestamps.
    op.execute(
        """
        INSERT INTO organization_invitations
            (id, organization_id, email_normalized, role, status, invited_by_user_id, created_at, updated_at,
             expires_at)
        SELECT m.id, m.organization_id, u.email_normalized, m.role, 'pending', m.invited_by_user_id,
               m.created_at, m.updated_at, now() + interval '7 days'
        FROM organization_members m
        JOIN users u ON u.id = m.user_id
        WHERE m.status = 'invited'
        """
    )
    op.execute("DELETE FROM organization_members WHERE status = 'invited'")


def downgrade() -> None:
    # Pending invitations whose email belongs to an account return as 'invited' member rows; those
    # addressed to emails without an account cannot be represented by the old model and are dropped.
    op.execute(
        """
        INSERT INTO organization_members
            (id, organization_id, user_id, role, status, invited_by_user_id, created_at, updated_at)
        SELECT i.id, i.organization_id, u.id, i.role, 'invited', i.invited_by_user_id, i.created_at, i.updated_at
        FROM organization_invitations i
        JOIN users u ON u.email_normalized = i.email_normalized
        WHERE i.status = 'pending'
          AND i.expires_at > now()
          AND NOT EXISTS (
              SELECT 1 FROM organization_members m
              WHERE m.organization_id = i.organization_id AND m.user_id = u.id
          )
        """
    )
    op.drop_index("uq_organization_invitations_org_pending_email", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_email_normalized", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_organization_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")

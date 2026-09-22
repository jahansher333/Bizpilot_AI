"""Internal trace events persistence schema.

Revision ID: 0004_internal_trace_events
Revises: 0003_organizations_and_members
Create Date: 2026-09-23 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004_internal_trace_events"
down_revision: Union[str, None] = "0003_organizations_and_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Restrictive foreign key delete semantics per Founder Decision FD-ORG006-01
    op.create_table(
        "internal_trace_events",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'denied', 'failed')",
            name="outcome",
        ),
        sa.CheckConstraint(
            "char_length(trim(action)) >= 3",
            name="action_len",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_internal_trace_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_internal_trace_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_internal_trace_events"),
    )
    op.create_index(
        "ix_internal_trace_events_organization_id",
        "internal_trace_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_internal_trace_events_org_created",
        "internal_trace_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_internal_trace_events_request_id",
        "internal_trace_events",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_internal_trace_events_request_id", table_name="internal_trace_events")
    op.drop_index("ix_internal_trace_events_org_created", table_name="internal_trace_events")
    op.drop_index("ix_internal_trace_events_organization_id", table_name="internal_trace_events")
    op.drop_table("internal_trace_events")

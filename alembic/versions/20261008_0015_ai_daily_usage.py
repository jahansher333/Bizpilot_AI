"""Daily assistant request counter per organization (SEC-P1 F4).

Revision ID: 0015_ai_daily_usage
Revises: 0014_auth_rate_limits
Create Date: 2026-10-08 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0015_ai_daily_usage"
down_revision: Union[str, None] = "0014_auth_rate_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Counts only: no prompt content or user data lives here.
    op.create_table(
        "ai_daily_usage",
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_ai_daily_usage_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "request_count >= 0", name=op.f("ck_ai_daily_usage_request_count_nonnegative")
        ),
        sa.PrimaryKeyConstraint("organization_id", "usage_date", name="pk_ai_daily_usage"),
    )


def downgrade() -> None:
    op.drop_table("ai_daily_usage")

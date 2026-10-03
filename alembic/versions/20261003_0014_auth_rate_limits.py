"""Auth rate-limit counters for login and password recovery (FIX-003).

Revision ID: 0014_auth_rate_limits
Revises: 0013_ai_metadata
Create Date: 2026-10-03 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0014_auth_rate_limits"
down_revision: Union[str, None] = "0013_ai_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Subjects (email/IP) are stored only as SHA-256 digests; no tenant data lives here.
    op.create_table(
        "auth_rate_limit_buckets",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        sa.PrimaryKeyConstraint("scope", "key_hash", name="pk_auth_rate_limit_buckets"),
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_updated_at",
        "auth_rate_limit_buckets",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_buckets_updated_at", table_name="auth_rate_limit_buckets")
    op.drop_table("auth_rate_limit_buckets")

"""Idempotency keys persistence schema.

Revision ID: 0008_idempotency_keys
Revises: 0007_inventory
Create Date: 2026-09-24 04:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_idempotency_keys"
down_revision: Union[str, None] = "0007_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_idempotency_keys_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_idempotency_keys_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'completed'"),
        ),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_keys_org_user_op_key",
        ),
    )
    op.create_index(
        "ix_idempotency_keys_lookup",
        "idempotency_keys",
        ["organization_id", "user_id", "operation", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_lookup", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

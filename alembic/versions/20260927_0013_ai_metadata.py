"""AI metadata and tool call observability schema (AI-007).

Revision ID: 0013_ai_metadata
Revises: 0012_expenses
Create Date: 2026-09-27 02:20:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0013_ai_metadata"
down_revision: Union[str, None] = "0012_expenses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. AI Interactions Table
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_ai_interactions_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_ai_interactions_user_id_users",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("trace_id", sa.String(100), nullable=False),
        sa.Column("model_identifier", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_pkr_minor", sa.BigInteger(), nullable=True),
        sa.Column("error_category", sa.String(50), nullable=True),
        sa.Column(
            "has_grounded_provenance",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success', 'error', 'timeout', 'provider_unavailable', 'max_turns_exceeded', 'disabled')",
            name="check_ai_interactions_status",
        ),
        sa.CheckConstraint(
            "latency_ms >= 0",
            name="check_ai_interactions_latency_nonnegative",
        ),
    )
    op.create_index("ix_ai_interactions_organization_id", "ai_interactions", ["organization_id"])
    op.create_index("ix_ai_interactions_user_id", "ai_interactions", ["user_id"])
    op.create_index("ix_ai_interactions_trace_id", "ai_interactions", ["trace_id"])
    op.create_index(
        "ix_ai_interactions_org_created",
        "ai_interactions",
        ["organization_id", "created_at"],
    )

    # 2. AI Tool Calls Table
    op.create_table(
        "ai_tool_calls",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ai_interaction_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "ai_interactions.id",
                name="fk_ai_tool_calls_ai_interaction_id_ai_interactions",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "organizations.id",
                name="fk_ai_tool_calls_organization_id_organizations",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("authorization_result", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("error_category", sa.String(50), nullable=True),
        sa.Column("provenance_tool", sa.String(100), nullable=True),
        sa.Column("provenance_period", sa.String(50), nullable=True),
        sa.Column("provenance_method", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "authorization_result IN ('allowed', 'denied')",
            name="check_ai_tool_calls_auth_result",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'error', 'denied')",
            name="check_ai_tool_calls_status",
        ),
        sa.CheckConstraint(
            "latency_ms >= 0",
            name="check_ai_tool_calls_latency_nonnegative",
        ),
    )
    op.create_index("ix_ai_tool_calls_interaction_id", "ai_tool_calls", ["ai_interaction_id"])
    op.create_index("ix_ai_tool_calls_organization_id", "ai_tool_calls", ["organization_id"])
    op.create_index(
        "ix_ai_tool_calls_org_tool",
        "ai_tool_calls",
        ["organization_id", "tool_name"],
    )
    op.create_index("ix_ai_tool_calls_created_at", "ai_tool_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_tool_calls")
    op.drop_table("ai_interactions")

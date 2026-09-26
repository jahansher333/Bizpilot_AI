"""SQLAlchemy models for tenant-scoped AI metadata and observability (AI-007).

Adheres strictly to docs/architecture/DATABASE-DESIGN.md Section 26 and
docs/architecture/AI-ARCHITECTURE.md Section 27:
- Minimal metadata only: latency, model, tokens, error categories, tool outcomes, provenance.
- Privacy-first: Raw prompts, assistant responses, and unredacted customer data are NEVER persisted.
- Tenant isolation: All records are strictly bound to organization_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


class AIInteraction(Base):
    """Minimal metadata record of an AI Assistant execution cycle.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    Does NOT store raw prompt text or raw assistant responses.
    """

    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_ai_interactions_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_ai_interactions_user_id_users",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Optional usage / accounting metadata
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_pkr_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Safe error category and provenance indicator
    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_grounded_provenance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    tool_calls: Mapped[list[AIToolCall]] = relationship(
        "AIToolCall",
        back_populates="interaction",
        cascade="all, delete-orphan",
        order_by="AIToolCall.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'error', 'timeout', 'provider_unavailable', 'max_turns_exceeded', 'disabled')",
            name="check_ai_interactions_status",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="check_ai_interactions_latency_nonnegative",
        ),
        Index("ix_ai_interactions_organization_id", "organization_id"),
        Index("ix_ai_interactions_user_id", "user_id"),
        Index("ix_ai_interactions_trace_id", "trace_id"),
        Index("ix_ai_interactions_org_created", "organization_id", "created_at"),
    )


class AIToolCall(Base):
    """Metadata record of an individual tool execution invoked during an AI cycle.

    Satisfies TenantScopedModel protocol (`id`, `organization_id`).
    Does NOT store raw function arguments or raw execution payloads.
    """

    __tablename__ = "ai_tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ai_interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "ai_interactions.id",
            name="fk_ai_tool_calls_ai_interaction_id_ai_interactions",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_ai_tool_calls_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    authorization_result: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Provenance metadata (which deterministic tool and method provided grounding)
    provenance_tool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provenance_period: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provenance_method: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    interaction: Mapped[AIInteraction] = relationship(
        "AIInteraction",
        back_populates="tool_calls",
    )

    __table_args__ = (
        CheckConstraint(
            "authorization_result IN ('allowed', 'denied')",
            name="check_ai_tool_calls_auth_result",
        ),
        CheckConstraint(
            "status IN ('success', 'error', 'denied')",
            name="check_ai_tool_calls_status",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="check_ai_tool_calls_latency_nonnegative",
        ),
        Index("ix_ai_tool_calls_interaction_id", "ai_interaction_id"),
        Index("ix_ai_tool_calls_organization_id", "organization_id"),
        Index("ix_ai_tool_calls_org_tool", "organization_id", "tool_name"),
        Index("ix_ai_tool_calls_created_at", "created_at"),
    )

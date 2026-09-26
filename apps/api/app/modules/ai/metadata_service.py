"""AI metadata recording and tenant-scoped retrieval service (AI-007).

Enforces:
- Authoritative server-owned tenant binding (context.organization_id and context.user.id).
- Privacy-first minimization: No raw prompt, no raw assistant response, and no raw tool arguments.
- Redaction of sensitive fields and clean error categorization.
- Cross-tenant IDOR protection on retrieval.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.models import AIInteraction, AIToolCall
from app.modules.ai.redaction import redact_sensitive_text, sanitize_error_category
from app.modules.ai.schemas import ProvenanceMeta, ToolCallMetadata
from app.modules.organizations.context import RequestContext

logger = logging.getLogger("bizpilot.ai.metadata")


class AIMetadataService:
    """Service for persisting and querying tenant-isolated AI observability metadata."""

    @classmethod
    async def record_interaction(
        cls,
        session: AsyncSession,
        context: RequestContext,
        trace_id: str,
        model_identifier: str,
        status: str,
        latency_ms: float,
        tool_calls: list[ToolCallMetadata] | None = None,
        provenance: list[ProvenanceMeta] | None = None,
        error_category: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost_pkr_minor: int | None = None,
    ) -> AIInteraction:
        """Persist minimal metadata for an AI Assistant interaction cycle."""
        # 1. Authoritative context binding (ignoring any untrusted client/model input)
        org_id = context.organization_id
        user_id = context.user.id if context.user else None

        tool_calls_list = tool_calls or []
        provenance_list = provenance or []
        has_provenance = len(provenance_list) > 0

        # Safe status classification
        valid_statuses = {
            "success",
            "error",
            "timeout",
            "provider_unavailable",
            "max_turns_exceeded",
            "disabled",
        }
        normalized_status = status if status in valid_statuses else "error"

        # 2. Build AIInteraction record
        interaction = AIInteraction(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user_id,
            trace_id=redact_sensitive_text(trace_id),
            model_identifier=redact_sensitive_text(model_identifier),
            status=normalized_status,
            latency_ms=max(0.0, float(latency_ms)),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_pkr_minor=estimated_cost_pkr_minor,
            error_category=redact_sensitive_text(error_category) if error_category else None,
            has_grounded_provenance=has_provenance,
        )

        res = session.add(interaction)
        if asyncio.iscoroutine(res):
            await res

        # 3. Build child AIToolCall records (without raw arguments or responses)
        provenance_by_tool: dict[str, ProvenanceMeta] = {
            p.source_tool: p for p in provenance_list if p.source_tool
        }

        for tc in tool_calls_list:
            auth_result = "denied" if tc.status == "denied" else "allowed"
            tc_status = "denied" if tc.status == "denied" else ("error" if tc.status == "error" else "success")
            tc_prov = provenance_by_tool.get(tc.tool_name)

            tool_call_row = AIToolCall(
                id=uuid.uuid4(),
                ai_interaction_id=interaction.id,
                organization_id=org_id,
                tool_name=redact_sensitive_text(tc.tool_name),
                authorization_result=auth_result,
                status=tc_status,
                latency_ms=max(0.0, float(tc.latency_ms)),
                error_category="authorization_denied" if tc.status == "denied" else (
                    "tool_error" if tc.status == "error" else None
                ),
                provenance_tool=tc_prov.source_tool if tc_prov else None,
                provenance_period=tc_prov.period_applied if tc_prov else None,
                provenance_method=tc_prov.calculation_method if tc_prov else None,
            )
            tc_res = session.add(tool_call_row)
            if asyncio.iscoroutine(tc_res):
                await tc_res

        await session.flush()
        return interaction

    @classmethod
    async def get_interaction(
        cls,
        session: AsyncSession,
        context: RequestContext,
        interaction_id: UUID,
    ) -> AIInteraction | None:
        """Fetch an AI interaction by ID with strict tenant isolation."""
        stmt = (
            select(AIInteraction)
            .options(selectinload(AIInteraction.tool_calls))
            .where(
                AIInteraction.id == interaction_id,
                AIInteraction.organization_id == context.organization_id,
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def list_interactions(
        cls,
        session: AsyncSession,
        context: RequestContext,
        limit: int = 50,
    ) -> Sequence[AIInteraction]:
        """List AI interactions for the current tenant in descending order."""
        bounded_limit = max(1, min(limit, 100))
        stmt = (
            select(AIInteraction)
            .options(selectinload(AIInteraction.tool_calls))
            .where(AIInteraction.organization_id == context.organization_id)
            .order_by(AIInteraction.created_at.desc())
            .limit(bounded_limit)
        )
        res = await session.execute(stmt)
        return res.scalars().all()

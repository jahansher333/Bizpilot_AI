"""FastAPI router for BizPilot AI Assistant (AI-008).

Exposes the authoritative single BizPilot Assistant endpoint behind
server-verified RequestContext and RBAC permissions.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.assistant import BizPilotAssistantOrchestrator
from app.modules.ai.schemas import AssistantRequest, AssistantResponse
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

ai_router = APIRouter(
    prefix="/organizations/{organization_id}/ai",
    tags=["ai"],
)

_ORCHESTRATOR = BizPilotAssistantOrchestrator()


@ai_router.post(
    "/chat",
    response_model=AssistantResponse,
    status_code=status.HTTP_200_OK,
    summary="Query BizPilot AI Assistant",
    description=(
        "Executes a single conversational turn with the read-only BizPilot AI Assistant. "
        "Enforces server-verified tenant isolation and role-filtered tool execution. "
        "Financial figures are grounded strictly in deterministic backend services."
    ),
)
async def chat_with_assistant(
    organization_id: uuid.UUID,
    request: AssistantRequest,
    context: RequestContext = Depends(require_permission(Permission.AI_QUERY_STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AssistantResponse:
    """Chat with BizPilot AI Assistant within trusted organization scope."""
    org_name = context.organization.display_name if context.organization else None
    return await _ORCHESTRATOR.run_turn(
        session=session,
        context=context,
        request=request,
        org_name=org_name,
    )

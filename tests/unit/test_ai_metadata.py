"""Unit tests for AI Metadata, Usage Tracking, Redacted Tracing, and Observability (AI-007).

Tests at minimum:
1. successful interaction metadata
2. tool-call metadata
3. organization isolation
4. authenticated user binding
5. provider/model metadata
6. execution latency metadata
7. token/usage metadata when available
8. authorization-denied metadata
9. timeout metadata
10. provider-outage metadata
11. secret redaction
12. Authorization header redaction
13. raw prompt not persisted by default
14. raw assistant response not persisted by default
15. raw tool arguments/results not persisted by default
16. provenance/tool-name tracking
17. cross-tenant metadata access denied
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agents import MaxTurnsExceeded, Runner, RunResult
from pydantic import SecretStr

from app.core.config import AISettings
from app.modules.ai.assistant import BizPilotAssistantOrchestrator
from app.modules.ai.exceptions import (
    AIDisabledException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai.metadata_service import AIMetadataService
from app.modules.ai.models import AIInteraction, AIToolCall
from app.modules.ai.provider import AIProviderAdapter
from app.modules.ai.redaction import (
    redact_dict,
    redact_sensitive_text,
    sanitize_error_category,
)
from app.modules.ai.schemas import (
    AssistantRequest,
    ProvenanceMeta,
    ToolCallMetadata,
)
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.context import OrganizationContext, RequestContext
from app.modules.organizations.enums import MemberRole, OrganizationStatus


def make_test_context(org_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None) -> RequestContext:
    return RequestContext(
        user=AuthenticatedUser(
            id=user_id or uuid4(),
            email_normalized="owner@bizpilot.test",
            display_name="Owner User",
            status="active",
        ),
        organization=OrganizationContext(
            id=org_id or uuid4(),
            display_name="Test Fabrics Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status=OrganizationStatus.ACTIVE.value,
        ),
        membership_id=uuid4(),
        role=MemberRole.OWNER,
    )


@pytest.fixture
def test_context() -> RequestContext:
    return make_test_context()


@pytest.fixture
def enabled_provider() -> AIProviderAdapter:
    settings = AISettings(
        enabled=True,
        api_key=SecretStr("sk-test-key-1234567890abcdef"),
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        max_tool_calls=5,
        log_raw_prompts=False,
    )
    return AIProviderAdapter(settings)


# -------------------------------------------------------------------------
# 11 & 12: Redaction Tests (Secrets, Bearer tokens, DB credentials)
# -------------------------------------------------------------------------

def test_secret_and_token_redaction() -> None:
    raw_text = (
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signature\n"
        "Standalone: sk-proj-1234567890abcdef12345678\n"
        "password: 'MySecretPassword123'\n"
        "DB: postgresql+asyncpg://admin:super_secret_pw@localhost:5432/bizpilot"
    )
    redacted = redact_sensitive_text(raw_text)

    assert "Bearer [REDACTED]" in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "[API_KEY_REDACTED]" in redacted
    assert "sk-proj" not in redacted
    assert 'password="[REDACTED]"' in redacted
    assert "MySecretPassword123" not in redacted
    assert "super_secret_pw" not in redacted
    assert "[REDACTED]:[REDACTED]@" in redacted


def test_redact_dict_preserves_clean_data_and_masks_sensitive_keys() -> None:
    payload = {
        "user": "Alice",
        "role": "owner",
        "authorization": "Bearer secret-token-xyz",
        "password": "plain-password",
        "nested": {
            "api_key": "sk-1234567890123456789012345",
            "safe_metric": 42,
        },
    }
    cleaned = redact_dict(payload)

    assert cleaned["user"] == "Alice"
    assert cleaned["role"] == "owner"
    assert cleaned["authorization"] == "[REDACTED]"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["safe_metric"] == 42


# -------------------------------------------------------------------------
# 1, 2, 3, 4, 5, 6, 7, 13, 14, 15, 16: Metadata Recording & Isolation
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_interaction_and_tool_call_metadata(test_context: RequestContext) -> None:
    session = AsyncMock()
    added_objects: list[object] = []
    session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    tool_call = ToolCallMetadata(
        tool_name="get_sales_summary",
        arguments={"period": "today"},
        latency_ms=125.5,
        status="success",
    )
    prov = ProvenanceMeta(
        source_tool="get_sales_summary",
        period_applied="today",
        calculation_method="deterministic_service",
    )

    interaction = await AIMetadataService.record_interaction(
        session=session,
        context=test_context,
        trace_id="trc_test_001",
        model_identifier="gpt-4o-mini",
        status="success",
        latency_ms=450.2,
        tool_calls=[tool_call],
        provenance=[prov],
        prompt_tokens=150,
        completion_tokens=50,
        total_tokens=200,
        estimated_cost_pkr_minor=1200,
    )

    # 1. Successful interaction metadata
    assert interaction.status == "success"
    assert interaction.trace_id == "trc_test_001"

    # 3. Organization isolation
    assert interaction.organization_id == test_context.organization_id

    # 4. Authenticated user binding
    assert interaction.user_id == test_context.user.id

    # 5. Provider/model metadata
    assert interaction.model_identifier == "gpt-4o-mini"

    # 6. Execution latency metadata
    assert interaction.latency_ms == 450.2

    # 7. Token/usage metadata
    assert interaction.prompt_tokens == 150
    assert interaction.completion_tokens == 50
    assert interaction.total_tokens == 200
    assert interaction.estimated_cost_pkr_minor == 1200

    # 16. Provenance indicator
    assert interaction.has_grounded_provenance is True

    # 13 & 14. Raw prompt and raw assistant response NOT persisted on interaction model
    assert not hasattr(AIInteraction, "prompt")
    assert not hasattr(AIInteraction, "raw_prompt")
    assert not hasattr(AIInteraction, "response")
    assert not hasattr(AIInteraction, "raw_response")
    assert not hasattr(interaction, "prompt")

    # 2. Tool-call metadata verification
    tool_call_rows = [obj for obj in added_objects if isinstance(obj, AIToolCall)]
    assert len(tool_call_rows) == 1
    tc_row = tool_call_rows[0]
    assert tc_row.ai_interaction_id == interaction.id
    assert tc_row.organization_id == test_context.organization_id
    assert tc_row.tool_name == "get_sales_summary"
    assert tc_row.authorization_result == "allowed"
    assert tc_row.status == "success"
    assert tc_row.latency_ms == 125.5
    assert tc_row.provenance_tool == "get_sales_summary"
    assert tc_row.provenance_period == "today"
    assert tc_row.provenance_method == "deterministic_service"

    # 15. Raw tool arguments/results NOT persisted on tool call row
    assert not hasattr(AIToolCall, "arguments")
    assert not hasattr(AIToolCall, "result")
    assert not hasattr(AIToolCall, "raw_result")
    assert not hasattr(tc_row, "arguments")


# -------------------------------------------------------------------------
# 8. Authorization Denied Metadata
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authorization_denied_metadata(test_context: RequestContext) -> None:
    session = AsyncMock()
    added_objects: list[object] = []
    session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    denied_tool_call = ToolCallMetadata(
        tool_name="get_expense_summary",
        arguments={},
        latency_ms=10.0,
        status="denied",
    )

    interaction = await AIMetadataService.record_interaction(
        session=session,
        context=test_context,
        trace_id="trc_denied_001",
        model_identifier="gpt-4o-mini",
        status="success",
        latency_ms=200.0,
        tool_calls=[denied_tool_call],
        provenance=[],
        error_category="authorization_denied",
    )

    tool_call_rows = [obj for obj in added_objects if isinstance(obj, AIToolCall)]
    assert len(tool_call_rows) == 1
    tc = tool_call_rows[0]
    assert tc.authorization_result == "denied"
    assert tc.status == "denied"
    assert tc.error_category == "authorization_denied"


# -------------------------------------------------------------------------
# 9. Timeout Metadata
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_metadata(test_context: RequestContext) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    interaction = await AIMetadataService.record_interaction(
        session=session,
        context=test_context,
        trace_id="trc_timeout_001",
        model_identifier="gpt-4o-mini",
        status="timeout",
        latency_ms=10005.0,
        tool_calls=[],
        provenance=[],
        error_category="timeout",
    )

    assert interaction.status == "timeout"
    assert interaction.error_category == "timeout"
    assert interaction.latency_ms == 10005.0


# -------------------------------------------------------------------------
# 10. Provider Outage Metadata
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provider_outage_metadata(test_context: RequestContext) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    interaction = await AIMetadataService.record_interaction(
        session=session,
        context=test_context,
        trace_id="trc_outage_001",
        model_identifier="gpt-4o-mini",
        status="provider_unavailable",
        latency_ms=150.0,
        tool_calls=[],
        provenance=[],
        error_category="provider_unavailable",
    )

    assert interaction.status == "provider_unavailable"
    assert interaction.error_category == "provider_unavailable"


# -------------------------------------------------------------------------
# 17. Cross-Tenant Metadata Access Denied
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_metadata_access_denied() -> None:
    session = AsyncMock()
    org1_context = make_test_context(org_id=uuid4())
    org2_context = make_test_context(org_id=uuid4())
    interaction_id = uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    # Request from org2 for org1's interaction
    fetched = await AIMetadataService.get_interaction(
        session=session,
        context=org2_context,
        interaction_id=interaction_id,
    )

    assert fetched is None
    # Verify execute called with where clause restricting to org2
    executed_stmt = session.execute.call_args[0][0]
    where_clause_str = str(executed_stmt)
    assert "ai_interactions.organization_id =" in where_clause_str


# -------------------------------------------------------------------------
# Orchestrator Integration with Metadata Tracking
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_turn_populates_metadata_and_provenance(
    test_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    session = AsyncMock()
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="What is our status?")

    mock_run_result = RunResult(
        input=request.message,
        new_items=[],
        raw_responses=[
            MagicMock(
                usage=MagicMock(input_tokens=80, output_tokens=30, total_tokens=110)
            )
        ],
        final_output="All operations are running smoothly.",
        input_guardrail_results=[],
        output_guardrail_results=[],
        _last_agent=MagicMock(),
    )

    with patch.object(Runner, "run", new_callable=AsyncMock) as mock_runner:
        mock_runner.return_value = mock_run_result
        with patch.object(AIMetadataService, "record_interaction", new_callable=AsyncMock) as mock_record:
            mock_interaction = MagicMock(id=uuid4())
            mock_record.return_value = mock_interaction

            resp = await orchestrator.run_turn(
                session=session,
                context=test_context,
                request=request,
            )

    assert resp.content == "All operations are running smoothly."
    assert resp.trace_id is not None
    assert resp.interaction_id == mock_interaction.id
    mock_record.assert_called_once()
    record_kwargs = mock_record.call_args.kwargs
    assert record_kwargs["status"] == "success"
    assert record_kwargs["prompt_tokens"] == 80
    assert record_kwargs["completion_tokens"] == 30
    assert record_kwargs["total_tokens"] == 110


@pytest.mark.asyncio
async def test_orchestrator_timeout_records_timeout_metadata(
    test_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    session = AsyncMock()
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Long request")

    with patch.object(Runner, "run", side_effect=AITimeoutException("Timeout occurred")):
        with patch.object(AIMetadataService, "record_interaction", new_callable=AsyncMock) as mock_record:
            mock_interaction = MagicMock(id=uuid4())
            mock_record.return_value = mock_interaction

            resp = await orchestrator.run_turn(
                session=session,
                context=test_context,
                request=request,
            )

    assert "timeout" in resp.content.lower()
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["status"] == "timeout"
    assert mock_record.call_args.kwargs["error_category"] == "timeout"

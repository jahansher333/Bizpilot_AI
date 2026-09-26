"""Unit tests for BizPilot AI Single Assistant Orchestration (AI-006).

Tests:
- direct non-tool conversation
- unsupported write request refusal
- unsupported forecasting refusal
- single-tool execution
- multi-tool execution
- no-data result
- permission denial
- cross-tenant attempt
- model-supplied organization override attempt
- max-turn safety
- provider timeout
- provider outage
- sensitive tracing disabled
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agents import MaxTurnsExceeded, RunConfig, RunContextWrapper, Runner, RunResult
from pydantic import SecretStr

from app.core.config import AISettings
from app.modules.ai.assistant import (
    AssistantRuntimeContext,
    BizPilotAssistantOrchestrator,
    _make_sdk_tool_invoker,
    build_sdk_function_tools,
    build_system_message,
)
from app.modules.ai.exceptions import (
    AIDisabledException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai.provider import AIProviderAdapter
from app.modules.ai.schemas import (
    AssistantMessage,
    AssistantRequest,
    ProvenanceMeta,
    SalesSummaryResult,
    SalesSummaryValues,
    ToolCallMetadata,
    ToolErrorCode,
)
from app.modules.ai.tools import AIToolRegistry
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.context import OrganizationContext, RequestContext
from app.modules.organizations.enums import MemberRole, OrganizationStatus


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def make_test_context(role: MemberRole) -> RequestContext:
    return RequestContext(
        user=AuthenticatedUser(
            id=uuid4(),
            email_normalized="test@bizpilot.test",
            display_name="Test User",
            status="active",
        ),
        organization=OrganizationContext(
            id=uuid4(),
            display_name="Test Fabrics Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status=OrganizationStatus.ACTIVE.value,
        ),
        membership_id=uuid4(),
        role=role,
    )


@pytest.fixture
def org_context() -> RequestContext:
    return make_test_context(MemberRole.OWNER)


@pytest.fixture
def staff_context() -> RequestContext:
    return make_test_context(MemberRole.STAFF)


@pytest.fixture
def enabled_provider() -> AIProviderAdapter:
    settings = AISettings(
        enabled=True,
        api_key=SecretStr("sk-test-key-12345"),
        model="gpt-4o-mini",
        timeout_seconds=10.0,
        max_tool_calls=5,
        log_raw_prompts=False,
    )
    return AIProviderAdapter(settings)


def test_build_system_message_bounds_and_context(org_context: RequestContext) -> None:
    msg = build_system_message(org_context, org_name="Test Fabrics")
    assert "BizPilot AI" in msg
    assert "READ-ONLY SCOPE" in msg
    assert "DETERMINISTIC FINANCIAL TRUTH" in msg
    assert "CURRENCY & NUMBER INTEGRITY" in msg
    assert "PKR" in msg
    assert "NO OUT-OF-SCOPE / P2 FEATURES" in msg
    assert "Test Fabrics" in msg
    assert "OWNER" in msg


def test_build_sdk_function_tools_coverage() -> None:
    tools = build_sdk_function_tools()
    expected_tools = {
        "get_sales_summary",
        "get_inventory_status",
        "get_customer_balance",
        "get_order_details",
        "get_top_products",
        "get_expense_summary",
        "get_payment_summary",
        "get_dashboard_summary",
    }
    assert set(tools.keys()) == expected_tools
    for name, tool in tools.items():
        assert tool.name == name
        assert tool.description
        assert tool.params_json_schema is not None
        assert not tool.strict_json_schema


@pytest.mark.asyncio
async def test_direct_non_tool_conversation(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Hello, how can you help me?")

    fake_result = RunResult(
        input=request.message,
        new_items=[],
        raw_responses=[],
        final_output="Hello! I am your BizPilot AI business assistant.",
        input_guardrail_results=[],
        output_guardrail_results=[],
        _last_agent=MagicMock(),
    )

    with patch.object(Runner, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = fake_result
        resp = await orchestrator.run_turn(
            session=mock_session,
            context=org_context,
            request=request,
            org_name="My SME",
        )

    assert resp.content == "Hello! I am your BizPilot AI business assistant."
    assert resp.tool_calls == []
    assert resp.provenance == []
    assert resp.model == "gpt-4o-mini"
    assert resp.latency_ms >= 0


@pytest.mark.asyncio
async def test_unsupported_write_and_forecasting_instructions(org_context: RequestContext) -> None:
    prompt = build_system_message(org_context)
    assert "READ-ONLY SCOPE" in prompt
    assert "refuse politely and explain that BizPilot AI is strictly read-only" in prompt
    assert "sales forecasting is not supported" in prompt


@pytest.mark.asyncio
async def test_single_tool_execution(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Aaj kitni sales hui?")

    async def fake_runner_impl(starting_agent, input, context, max_turns, run_config):
        sales_tool = next(t for t in starting_agent.tools if t.name == "get_sales_summary")
        wrapper = RunContextWrapper(context)
        await sales_tool.on_invoke_tool(wrapper, json.dumps({"period": "today"}))
        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output="Aaj ki total sales Rs. 25,000 hain (10 orders).",
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    mock_sales_result = SalesSummaryResult(
        success=True,
        currency="PKR",
        values=SalesSummaryValues(
            total_sales_minor=2500000,
            total_sales_pkr="25,000.00",
            active_orders_count=10,
            period="today",
        ),
        provenance=ProvenanceMeta(
            source_tool="get_sales_summary",
            period_applied="today",
            calculation_method="deterministic_service",
        ),
    )

    with patch.object(Runner, "run", side_effect=fake_runner_impl):
        with patch.object(
            AIToolRegistry,
            "execute_tool",
            new_callable=AsyncMock,
            return_value=mock_sales_result.model_dump(mode="json"),
        ):
            resp = await orchestrator.run_turn(
                session=mock_session,
                context=org_context,
                request=request,
            )

    assert "25,000" in resp.content
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].tool_name == "get_sales_summary"
    assert resp.tool_calls[0].status == "success"
    assert len(resp.provenance) == 1
    assert resp.provenance[0].source_tool == "get_sales_summary"


@pytest.mark.asyncio
async def test_multi_tool_execution(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Sales and stock status please.")

    async def fake_runner_impl(starting_agent, input, context, max_turns, run_config):
        wrapper = RunContextWrapper(context)
        sales_tool = next(t for t in starting_agent.tools if t.name == "get_sales_summary")
        inv_tool = next(t for t in starting_agent.tools if t.name == "get_inventory_status")

        await sales_tool.on_invoke_tool(wrapper, json.dumps({"period": "today"}))
        await inv_tool.on_invoke_tool(wrapper, json.dumps({"low_stock_only": True}))

        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output="Sales: Rs. 10,000. Low stock: 2 products.",
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    with patch.object(Runner, "run", side_effect=fake_runner_impl):
        with patch.object(
            AIToolRegistry,
            "execute_tool",
            new_callable=AsyncMock,
            return_value={"success": True, "provenance": {"source_tool": "test", "calculation_method": "deterministic"}},
        ):
            resp = await orchestrator.run_turn(
                session=mock_session,
                context=org_context,
                request=request,
            )

    assert len(resp.tool_calls) == 2
    assert resp.tool_calls[0].tool_name == "get_sales_summary"
    assert resp.tool_calls[1].tool_name == "get_inventory_status"
    assert len(resp.provenance) == 2


@pytest.mark.asyncio
async def test_no_data_result_handling(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Details for order ORD-99999?")

    async def fake_runner_impl(starting_agent, input, context, max_turns, run_config):
        tool = next(t for t in starting_agent.tools if t.name == "get_order_details")
        wrapper = RunContextWrapper(context)
        await tool.on_invoke_tool(wrapper, json.dumps({"order_number": "ORD-99999"}))
        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output="No matching recorded order found for ORD-99999.",
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    no_data_payload = {
        "success": True,
        "values": None,
        "provenance": {
            "source_tool": "get_order_details",
            "calculation_method": "deterministic_service",
            "caveats": ["Order not found"],
        },
    }

    with patch.object(Runner, "run", side_effect=fake_runner_impl):
        with patch.object(
            AIToolRegistry,
            "execute_tool",
            new_callable=AsyncMock,
            return_value=no_data_payload,
        ):
            resp = await orchestrator.run_turn(
                session=mock_session,
                context=org_context,
                request=request,
            )

    assert "No matching recorded order" in resp.content
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].tool_name == "get_order_details"
    assert resp.tool_calls[0].status == "success"


@pytest.mark.asyncio
async def test_permission_denial_for_staff(
    mock_session: AsyncMock,
    staff_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    available_tools = AIToolRegistry.get_available_tools(staff_context)
    available_names = {t["function"]["name"] for t in available_tools}
    assert "get_expense_summary" not in available_names

    # If an unauthorized tool is invoked directly through the SDK invoker callback
    invoker = _make_sdk_tool_invoker("get_expense_summary")
    ctx = AssistantRuntimeContext(session=mock_session, request_context=staff_context)
    wrapper = RunContextWrapper(ctx)

    raw_res = await invoker(wrapper, "{}")
    res = json.loads(raw_res)

    assert not res["success"]
    assert res["error"]["code"] == ToolErrorCode.AUTHORIZATION_DENIED.value
    assert len(ctx.executed_tool_calls) == 1
    assert ctx.executed_tool_calls[0].status == "denied"


@pytest.mark.asyncio
async def test_model_supplied_organization_override_neutralized(
    mock_session: AsyncMock,
    org_context: RequestContext,
) -> None:
    invoker = _make_sdk_tool_invoker("get_sales_summary")
    ctx = AssistantRuntimeContext(session=mock_session, request_context=org_context)
    wrapper = RunContextWrapper(ctx)

    fake_other_org = str(uuid4())
    injected_args = json.dumps({"organization_id": fake_other_org, "period": "today"})

    with patch.object(
        AIToolRegistry,
        "execute_tool",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_exec:
        await invoker(wrapper, injected_args)

        mock_exec.assert_called_once()
        call_context = mock_exec.call_args.kwargs["context"]
        assert call_context.organization_id == org_context.organization_id
        assert call_context.organization_id != fake_other_org


@pytest.mark.asyncio
async def test_max_turn_safety(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Run looping tools")

    with patch.object(Runner, "run", side_effect=MaxTurnsExceeded("Loop limit reached.")):
        resp = await orchestrator.run_turn(
            session=mock_session,
            context=org_context,
            request=request,
        )

    assert "maximum tool exploration limit" in resp.content.lower()


@pytest.mark.asyncio
async def test_provider_timeout_safe_fallback(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Any question")

    with patch.object(Runner, "run", side_effect=AITimeoutException("Request timed out.")):
        resp = await orchestrator.run_turn(
            session=mock_session,
            context=org_context,
            request=request,
        )

    assert "timed out" in resp.content.lower()


@pytest.mark.asyncio
async def test_provider_outage_safe_fallback(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Any question")

    with patch.object(
        Runner, "run", side_effect=AIProviderUnavailableException("AI provider unavailable.")
    ):
        resp = await orchestrator.run_turn(
            session=mock_session,
            context=org_context,
            request=request,
        )

    assert "unavailable" in resp.content.lower()


@pytest.mark.asyncio
async def test_sensitive_tracing_disabled_configuration(
    mock_session: AsyncMock,
    org_context: RequestContext,
    enabled_provider: AIProviderAdapter,
) -> None:
    orchestrator = BizPilotAssistantOrchestrator(enabled_provider)
    request = AssistantRequest(message="Check tracing config")

    captured_run_config: RunConfig | None = None

    async def fake_runner(starting_agent, input, context, max_turns, run_config):
        nonlocal captured_run_config
        captured_run_config = run_config
        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output="Tracing checked.",
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    with patch.object(Runner, "run", side_effect=fake_runner):
        await orchestrator.run_turn(
            session=mock_session,
            context=org_context,
            request=request,
        )

    assert captured_run_config is not None
    assert captured_run_config.trace_include_sensitive_data is False
    assert captured_run_config.tracing_disabled is True

"""Unit tests for AI tool definitions and runtime registry (AI-005)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.ai.schemas import (
    CustomerBalanceResult,
    CustomerBalanceValues,
    DashboardSummaryResult,
    ExpenseSummaryResult,
    ExpenseSummaryValues,
    InventoryStatusResult,
    InventoryStatusValues,
    OrderDetailsResult,
    OrderDetailsValues,
    PaymentSummaryResult,
    PaymentSummaryValues,
    ProvenanceMeta,
    SalesSummaryResult,
    SalesSummaryValues,
    ToolErrorCode,
    TopProductsResult,
    TopProductsValues,
)
from app.modules.ai.tools import OPENAI_TOOL_DEFINITIONS, AIToolRegistry
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.context import OrganizationContext, RequestContext
from app.modules.organizations.enums import MemberRole, OrganizationStatus


def make_context(role: MemberRole) -> RequestContext:
    return RequestContext(
        user=AuthenticatedUser(
            id=uuid4(),
            email_normalized="owner@bizpilot.test",
            display_name="Owner User",
            status="active",
        ),
        organization=OrganizationContext(
            id=uuid4(),
            display_name="Tools Test Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status=OrganizationStatus.ACTIVE.value,
        ),
        membership_id=uuid4(),
        role=role,
    )


def test_tool_definitions_catalog_count_and_names() -> None:
    assert len(OPENAI_TOOL_DEFINITIONS) == 8
    expected_names = {
        "get_sales_summary",
        "get_inventory_status",
        "get_customer_balance",
        "get_order_details",
        "get_top_products",
        "get_expense_summary",
        "get_payment_summary",
        "get_dashboard_summary",
    }
    actual_names = {defn["function"]["name"] for defn in OPENAI_TOOL_DEFINITIONS}
    assert actual_names == expected_names


def test_available_tools_role_filtering() -> None:
    owner_ctx = make_context(MemberRole.OWNER)
    owner_tools = AIToolRegistry.get_available_tools(owner_ctx)
    assert len(owner_tools) == 8

    manager_ctx = make_context(MemberRole.MANAGER)
    manager_tools = AIToolRegistry.get_available_tools(manager_ctx)
    assert len(manager_tools) == 8

    staff_ctx = make_context(MemberRole.STAFF)
    staff_tools = AIToolRegistry.get_available_tools(staff_ctx)
    assert len(staff_tools) == 7
    staff_tool_names = {t["function"]["name"] for t in staff_tools}
    assert "get_expense_summary" not in staff_tool_names


@pytest.mark.asyncio
async def test_staff_denied_when_executing_expense_tool() -> None:
    staff_ctx = make_context(MemberRole.STAFF)
    mock_session = AsyncMock()

    res = await AIToolRegistry.execute_tool(
        session=mock_session,
        context=staff_ctx,
        tool_name="get_expense_summary",
        arguments={"period": "today"},
    )
    assert res["success"] is False
    assert res["error"]["code"] == ToolErrorCode.AUTHORIZATION_DENIED


@pytest.mark.asyncio
async def test_validation_error_on_invalid_arguments() -> None:
    owner_ctx = make_context(MemberRole.OWNER)
    mock_session = AsyncMock()

    # Pass invalid limit (must be between 1 and 100)
    res = await AIToolRegistry.execute_tool(
        session=mock_session,
        context=owner_ctx,
        tool_name="get_inventory_status",
        arguments={"limit": 500},
    )
    assert res["success"] is False
    assert res["error"]["code"] == ToolErrorCode.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_sales_summary_execution_success() -> None:
    owner_ctx = make_context(MemberRole.OWNER)
    mock_session = AsyncMock()

    mock_res = SalesSummaryResult(
        success=True,
        values=SalesSummaryValues(
            total_sales_minor=100000,
            total_sales_pkr="Rs. 1,000.00",
            active_orders_count=3,
            period="today",
        ),
        provenance=ProvenanceMeta(source_tool="get_sales_summary"),
    )

    with patch(
        "app.modules.ai.services.AIDeterministicReadService.get_sales_summary",
        return_value=mock_res,
    ) as mock_get_sales:
        res = await AIToolRegistry.execute_tool(
            session=mock_session,
            context=owner_ctx,
            tool_name="get_sales_summary",
            arguments={"period": "today"},
        )
        assert res["success"] is True
        assert res["values"]["total_sales_minor"] == 100000
        mock_get_sales.assert_called_once()


@pytest.mark.asyncio
async def test_prompt_injection_tenant_override_in_tool_registry() -> None:
    owner_ctx = make_context(MemberRole.OWNER)
    mock_session = AsyncMock()
    attacker_org_id = uuid4()

    mock_res = InventoryStatusResult(
        success=True,
        values=InventoryStatusValues(
            total_products_tracked=5,
            low_stock_count=1,
            out_of_stock_count=0,
            items=[],
        ),
        provenance=ProvenanceMeta(source_tool="get_inventory_status"),
    )

    with patch(
        "app.modules.ai.services.AIDeterministicReadService.get_inventory_status",
        return_value=mock_res,
    ) as mock_inv:
        res = await AIToolRegistry.execute_tool(
            session=mock_session,
            context=owner_ctx,
            tool_name="get_inventory_status",
            arguments={"organization_id": str(attacker_org_id), "limit": 10},
        )
        assert res["success"] is True
        # Verify the service was called with the trusted org_id, NOT the attacker's org_id
        _, kwargs = mock_inv.call_args
        assert kwargs["organization_id"] == owner_ctx.organization_id
        assert kwargs["organization_id"] != attacker_org_id

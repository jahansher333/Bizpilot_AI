"""Unit tests for AI tool result, provenance, and structured contracts (AI-002)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.ai.schemas import (
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    CustomerBalanceInput,
    CustomerBalanceResult,
    CustomerBalanceValues,
    DashboardSummaryInput,
    DashboardSummaryResult,
    ExpenseSummaryInput,
    ExpenseSummaryResult,
    ExpenseSummaryValues,
    InventoryStatusInput,
    InventoryStatusResult,
    InventoryStatusValues,
    OrderDetailsInput,
    OrderDetailsResult,
    OrderDetailsValues,
    PaymentSummaryInput,
    PaymentSummaryResult,
    PaymentSummaryValues,
    ProductStockItem,
    ProvenanceMeta,
    SalesSummaryInput,
    SalesSummaryResult,
    SalesSummaryValues,
    ToolCallMetadata,
    ToolError,
    ToolErrorCode,
    TopProductsInput,
    TopProductsResult,
    TopProductsValues,
)
from app.modules.dashboard.timezone import DashboardPeriod


def test_provenance_defaults_and_immutability() -> None:
    meta = ProvenanceMeta(
        source_tool="get_sales_summary",
        period_applied="today",
        source_refs=["orders:2026-09-26"],
    )
    assert meta.source_tool == "get_sales_summary"
    assert meta.period_applied == "today"
    assert meta.calculation_method == "deterministic_service"
    assert meta.freshness_timestamp is not None
    assert meta.source_refs == ["orders:2026-09-26"]


def test_tool_error_structure() -> None:
    error = ToolError(
        code=ToolErrorCode.AUTHORIZATION_DENIED,
        message="Staff role is not authorized to access operating expenses.",
        details={"required_permission": "expenses:view"},
    )
    assert error.code == ToolErrorCode.AUTHORIZATION_DENIED
    assert "Staff role" in error.message
    assert error.details["required_permission"] == "expenses:view"


def test_sales_summary_input_and_result() -> None:
    valid_input = SalesSummaryInput(period=DashboardPeriod.TODAY)
    assert valid_input.period == DashboardPeriod.TODAY

    # Extra fields must be forbidden
    with pytest.raises(ValidationError):
        SalesSummaryInput(period=DashboardPeriod.TODAY, organization_id=uuid4())  # type: ignore

    res = SalesSummaryResult(
        success=True,
        values=SalesSummaryValues(
            total_sales_minor=125000,
            total_sales_pkr="Rs. 1,250.00",
            active_orders_count=5,
            period="today",
        ),
        provenance=ProvenanceMeta(source_tool="get_sales_summary", period_applied="today"),
    )
    assert res.success is True
    assert res.values.total_sales_minor == 125000
    assert res.currency == "PKR"


def test_inventory_status_input_bounds_and_result() -> None:
    # Limit bounds check
    with pytest.raises(ValidationError):
        InventoryStatusInput(limit=0)
    with pytest.raises(ValidationError):
        InventoryStatusInput(limit=101)

    inp = InventoryStatusInput(low_stock_only=True, limit=25)
    assert inp.low_stock_only is True
    assert inp.limit == 25

    item = ProductStockItem(
        product_id=uuid4(),
        product_name="Atta 10kg",
        sku="ATTA-10",
        unit="bag",
        current_stock=2,
        reorder_point=5,
        is_low_stock=True,
        is_out_of_stock=False,
    )
    res = InventoryStatusResult(
        values=InventoryStatusValues(
            total_products_tracked=1,
            low_stock_count=1,
            out_of_stock_count=0,
            items=[item],
        ),
        provenance=ProvenanceMeta(source_tool="get_inventory_status"),
    )
    assert res.values.low_stock_count == 1
    assert res.values.items[0].is_low_stock is True


def test_customer_balance_result() -> None:
    cust_id = uuid4()
    inp = CustomerBalanceInput(customer_id=cust_id)
    assert inp.customer_id == cust_id

    res = CustomerBalanceResult(
        values=CustomerBalanceValues(
            customer_id=cust_id,
            customer_name="Tariq Store",
            phone="+923001234567",
            total_orders_minor=500000,
            total_payments_minor=350000,
            outstanding_balance_minor=150000,
            outstanding_balance_pkr="Rs. 1,500.00",
            order_count=10,
            payment_count=7,
        ),
        provenance=ProvenanceMeta(source_tool="get_customer_balance"),
    )
    assert res.values.outstanding_balance_minor == 150000


def test_order_details_result_and_safe_error() -> None:
    order_id = uuid4()
    inp = OrderDetailsInput(order_id=order_id)
    assert inp.order_id == order_id

    # Simulated not-found / authorization failure
    err_res = OrderDetailsResult(
        success=False,
        error=ToolError(
            code=ToolErrorCode.NO_MATCHING_DATA,
            message="No order matching the provided criteria was found.",
        ),
        provenance=ProvenanceMeta(source_tool="get_order_details"),
    )
    assert err_res.success is False
    assert err_res.error.code == ToolErrorCode.NO_MATCHING_DATA
    assert err_res.values is None


def test_top_products_input_and_result() -> None:
    inp = TopProductsInput(period=DashboardPeriod.THIS_MONTH, metric="revenue", limit=5)
    assert inp.metric == "revenue"

    with pytest.raises(ValidationError):
        TopProductsInput(metric="unsupported")  # type: ignore


def test_expense_and_payment_summaries() -> None:
    exp_res = ExpenseSummaryResult(
        values=ExpenseSummaryValues(
            total_expenses_minor=200000,
            total_expenses_pkr="Rs. 2,000.00",
            expense_count=4,
            period="today",
            categories=[],
        ),
        provenance=ProvenanceMeta(source_tool="get_expense_summary", period_applied="today"),
    )
    assert exp_res.values.total_expenses_minor == 200000

    pay_res = PaymentSummaryResult(
        values=PaymentSummaryValues(
            total_payments_minor=180000,
            total_payments_pkr="Rs. 1,800.00",
            payment_count=3,
            period="today",
            channels=[],
        ),
        provenance=ProvenanceMeta(source_tool="get_payment_summary", period_applied="today"),
    )
    assert pay_res.values.total_payments_minor == 180000


def test_assistant_request_and_response_schemas() -> None:
    req = AssistantRequest(
        message="Aaj kitni sales hui?",
        conversation_history=[
            AssistantMessage(role="user", content="Hello"),
            AssistantMessage(role="assistant", content="How can I help you today?"),
        ],
    )
    assert len(req.conversation_history) == 2

    with pytest.raises(ValidationError):
        AssistantRequest(message="")  # min length 1

    resp = AssistantResponse(
        content="Aaj total sales Rs. 1,250.00 hain.",
        tool_calls=[
            ToolCallMetadata(
                tool_name="get_sales_summary",
                arguments={"period": "today"},
                latency_ms=42.5,
                status="success",
            )
        ],
        provenance=[
            ProvenanceMeta(
                source_tool="get_sales_summary",
                period_applied="today",
            )
        ],
        model="gpt-4o-mini",
        latency_ms=120.0,
    )
    assert len(resp.tool_calls) == 1
    assert resp.provenance[0].source_tool == "get_sales_summary"

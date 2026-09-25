"""Structured tool inputs, results, provenance, and assistant contracts (AI-002).

Authoritative definitions conforming to docs/architecture/AI-ARCHITECTURE.md:
- Deterministic Provenance metadata
- Typed error codes distinguishing validation, authorization denial, empty data, timeouts
- Strict Pydantic models for the 8 approved P0 tool contracts
- Assistant request and grounded response contracts
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.dashboard.timezone import DashboardPeriod


class ToolErrorCode(StrEnum):
    """Categorized error codes for AI tool invocations."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    NO_MATCHING_DATA = "NO_MATCHING_DATA"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(BaseModel):
    """Structured failure representation for tool calls."""
    model_config = ConfigDict(extra="forbid")

    code: ToolErrorCode
    message: str
    details: dict[str, Any] | None = None


class ProvenanceMeta(BaseModel):
    """Provenance and calculation metadata proving facts originate from deterministic services."""
    model_config = ConfigDict(extra="forbid")

    source_tool: str
    period_applied: str | None = None
    freshness_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    calculation_method: str = "deterministic_service"
    caveats: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


# -------------------------------------------------------------------------
# Tool Inputs (8 Approved Tools)
# -------------------------------------------------------------------------

class SalesSummaryInput(BaseModel):
    """Input for get_sales_summary."""
    model_config = ConfigDict(extra="forbid")

    period: DashboardPeriod = Field(
        default=DashboardPeriod.TODAY,
        description="Time period: today, yesterday, this_week, this_month, custom",
    )
    start_date: date | None = None
    end_date: date | None = None


class InventoryStatusInput(BaseModel):
    """Input for get_inventory_status."""
    model_config = ConfigDict(extra="forbid")

    low_stock_only: bool = Field(
        default=False,
        description="Filter to only products at or below their reorder point",
    )
    limit: int = Field(default=50, ge=1, le=100)


class CustomerBalanceInput(BaseModel):
    """Input for get_customer_balance."""
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    query: str | None = Field(
        default=None,
        description="Customer name or phone search string if customer_id is not known",
    )


class OrderDetailsInput(BaseModel):
    """Input for get_order_details."""
    model_config = ConfigDict(extra="forbid")

    order_id: UUID | None = None
    order_number: str | None = None


class TopProductsInput(BaseModel):
    """Input for get_top_products."""
    model_config = ConfigDict(extra="forbid")

    period: DashboardPeriod = Field(default=DashboardPeriod.THIS_MONTH)
    metric: Literal["quantity", "revenue"] = Field(
        default="revenue",
        description="Rank products by revenue (sales total) or quantity sold",
    )
    limit: int = Field(default=5, ge=1, le=20)


class ExpenseSummaryInput(BaseModel):
    """Input for get_expense_summary."""
    model_config = ConfigDict(extra="forbid")

    period: DashboardPeriod = Field(default=DashboardPeriod.TODAY)
    start_date: date | None = None
    end_date: date | None = None
    category_id: UUID | None = None


class PaymentSummaryInput(BaseModel):
    """Input for get_payment_summary."""
    model_config = ConfigDict(extra="forbid")

    period: DashboardPeriod = Field(default=DashboardPeriod.TODAY)
    start_date: date | None = None
    end_date: date | None = None
    channel: str | None = None


class DashboardSummaryInput(BaseModel):
    """Input for get_dashboard_summary."""
    model_config = ConfigDict(extra="forbid")

    period: DashboardPeriod = Field(default=DashboardPeriod.TODAY)
    start_date: date | None = None
    end_date: date | None = None


# -------------------------------------------------------------------------
# Tool Structured Outputs
# -------------------------------------------------------------------------

class SalesSummaryValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sales_minor: int
    total_sales_pkr: str
    active_orders_count: int
    period: str


class SalesSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: SalesSummaryValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class ProductStockItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    product_name: str
    sku: str
    unit: str
    current_stock: int
    reorder_point: int | None = None
    is_low_stock: bool
    is_out_of_stock: bool


class InventoryStatusValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_products_tracked: int
    low_stock_count: int
    out_of_stock_count: int
    items: list[ProductStockItem]


class InventoryStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    values: InventoryStatusValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class CustomerBalanceValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    customer_name: str
    phone: str | None
    total_orders_minor: int
    total_payments_minor: int
    outstanding_balance_minor: int
    outstanding_balance_pkr: str
    order_count: int
    payment_count: int


class CustomerBalanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: CustomerBalanceValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class OrderItemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class OrderDetailsValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID
    order_number: str
    status: str
    customer_name: str | None
    ordered_at: datetime
    order_total_minor: int
    order_total_pkr: str
    items: list[OrderItemDetail]


class OrderDetailsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: OrderDetailsValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class TopProductItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    product_name: str
    sku: str
    quantity_sold: int
    revenue_minor: int
    revenue_pkr: str


class TopProductsValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    metric: str
    items: list[TopProductItem]


class TopProductsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: TopProductsValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class ExpenseCategoryBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None
    category_name: str
    total_minor: int
    total_pkr: str
    count: int


class ExpenseSummaryValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_expenses_minor: int
    total_expenses_pkr: str
    expense_count: int
    period: str
    categories: list[ExpenseCategoryBreakdown]


class ExpenseSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: ExpenseSummaryValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class PaymentChannelBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    total_minor: int
    total_pkr: str
    count: int


class PaymentSummaryValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_payments_minor: int
    total_payments_pkr: str
    payment_count: int
    period: str
    channels: list[PaymentChannelBreakdown]


class PaymentSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: PaymentSummaryValues | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


class DashboardSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    currency: str = "PKR"
    values: dict[str, Any] | None = None
    provenance: ProvenanceMeta
    error: ToolError | None = None


# -------------------------------------------------------------------------
# Assistant Request / Response / Tracing Schemas
# -------------------------------------------------------------------------

class AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_history: list[AssistantMessage] = Field(default_factory=list)


class ToolCallMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any]
    latency_ms: float
    status: Literal["success", "denied", "error"]


class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    tool_calls: list[ToolCallMetadata] = Field(default_factory=list)
    provenance: list[ProvenanceMeta] = Field(default_factory=list)
    model: str
    latency_ms: float

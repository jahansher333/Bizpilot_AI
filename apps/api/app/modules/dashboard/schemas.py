"""Pydantic schemas for deterministic dashboard responses (DASH-001, DASH-002)."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SalesSummaryDTO(BaseModel):
    """Aggregate metrics for recorded sales orders in the selected period."""

    model_config = ConfigDict(extra="forbid")

    order_count: int = Field(default=0, ge=0)
    total_sales_minor: int = Field(default=0, ge=0)
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)


class PaymentsSummaryDTO(BaseModel):
    """Aggregate metrics for recorded payments collected in the selected period."""

    model_config = ConfigDict(extra="forbid")

    payment_count: int = Field(default=0, ge=0)
    total_collected_minor: int = Field(default=0, ge=0)
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)


class ExpensesSummaryDTO(BaseModel):
    """Aggregate metrics for operating expenses recorded in the selected period."""

    model_config = ConfigDict(extra="forbid")

    expense_count: int = Field(default=0, ge=0)
    total_expenses_minor: int = Field(default=0, ge=0)
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)


class NetCashSummaryDTO(BaseModel):
    """Net operational cash flow (collections minus expenses) for authorized roles.

    Explicit non-goal: Does not represent profit, tax liability, or reconciled bank cash.
    """

    model_config = ConfigDict(extra="forbid")

    net_cash_minor: int
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)
    note: str = Field(
        default="Net operational receipts minus operating expenses. Does not imply net profit or tax liability."
    )


class LowStockItemDTO(BaseModel):
    """Product stock status indicator for inventory falling below threshold."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    product_code: str
    product_name: str
    base_unit: str
    on_hand_quantity: int
    is_out_of_stock: bool


class InventorySummaryDTO(BaseModel):
    """Operational stock indicators and list of low stock items."""

    model_config = ConfigDict(extra="forbid")

    low_stock_count: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)
    items: list[LowStockItemDTO] = Field(default_factory=list)


class RecentActivityItemDTO(BaseModel):
    """Lightweight operational activity feed item with source linkage."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    activity_type: str = Field(description="'order', 'payment', or 'expense'")
    reference_code: str
    amount_minor: int
    currency_code: str
    timestamp: datetime
    status: str
    description: str | None = None


class DashboardFreshnessDTO(BaseModel):
    """Metadata regarding period bounds, timezone context, and freshness timestamp."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    period: str
    local_start_date: str
    local_end_date: str
    timezone: str


class DashboardSummaryDTO(BaseModel):
    """Authoritative deterministic dashboard read contract (DASH-001, DASH-002)."""

    model_config = ConfigDict(extra="forbid")

    sales: SalesSummaryDTO
    payments: PaymentsSummaryDTO
    expenses: ExpensesSummaryDTO | None = None
    net_cash: NetCashSummaryDTO | None = None
    inventory: InventorySummaryDTO
    recent_activity: list[RecentActivityItemDTO] = Field(default_factory=list)
    freshness: DashboardFreshnessDTO

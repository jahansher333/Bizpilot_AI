"""Deterministic read services for BizPilot AI Assistant (AI-004).

Exposes approved read services to AI function tools:
- Queries execute strictly within server-verified organization_id.
- Money and arithmetic values remain integer minor units internally.
- Voided and inactive records are strictly excluded from aggregates.
- Provenance metadata is generated for every result.
- Reuses existing domain models and DashboardQueryService.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.schemas import (
    CustomerBalanceResult,
    CustomerBalanceValues,
    DashboardSummaryResult,
    ExpenseCategoryBreakdown,
    ExpenseSummaryResult,
    ExpenseSummaryValues,
    InventoryStatusResult,
    InventoryStatusValues,
    OrderDetailsResult,
    OrderDetailsValues,
    OrderItemDetail,
    PaymentChannelBreakdown,
    PaymentSummaryResult,
    PaymentSummaryValues,
    ProductStockItem,
    ProvenanceMeta,
    SalesSummaryResult,
    SalesSummaryValues,
    ToolError,
    ToolErrorCode,
    TopProductItem,
    TopProductsResult,
    TopProductsValues,
)
from app.modules.customers.models import Customer
from app.modules.dashboard.service import DashboardQueryService
from app.modules.dashboard.timezone import DashboardPeriod, resolve_period_range
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.inventory.models import InventoryBalance
from app.modules.orders.models import Order, OrderItem
from app.modules.organizations.enums import MemberRole
from app.modules.payments.models import Payment
from app.modules.products.models import Product

logger = logging.getLogger("bizpilot.ai.services")


def format_pkr(minor: int) -> str:
    """Format integer minor units into human readable PKR string."""
    sign = "-" if minor < 0 else ""
    abs_minor = abs(minor)
    major = abs_minor // 100
    cents = abs_minor % 100
    return f"{sign}Rs. {major:,}.{cents:02d}"


class AIDeterministicReadService:
    """Provides authoritative, tenant-scoped deterministic reads for AI tools."""

    @classmethod
    async def get_sales_summary(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        period: DashboardPeriod = DashboardPeriod.TODAY,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SalesSummaryResult:
        """Calculate sales total and active order count for an authorized period."""
        range_info = resolve_period_range(
            period=period,
            tz_name="Asia/Karachi",
            custom_start_date=start_date,
            custom_end_date=end_date,
        )
        start_utc = range_info.start_utc
        end_utc = range_info.end_utc

        query = (
            select(
                func.coalesce(func.sum(Order.order_total_minor), 0).label("total_sales"),
                func.count(Order.id).label("active_count"),
            )
            .where(Order.organization_id == organization_id)
            .where(Order.status != "voided")
            .where(Order.ordered_at >= start_utc)
            .where(Order.ordered_at < end_utc)
        )
        result = await session.execute(query)
        total_sales, count = result.one()

        return SalesSummaryResult(
            success=True,
            values=SalesSummaryValues(
                total_sales_minor=int(total_sales),
                total_sales_pkr=format_pkr(int(total_sales)),
                active_orders_count=int(count),
                period=period.value,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_sales_summary",
                period_applied=period.value,
                source_refs=[f"orders:{period.value}"],
                caveats=["Excludes voided orders"],
            ),
        )

    @classmethod
    async def get_inventory_status(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        low_stock_only: bool = False,
        limit: int = 50,
    ) -> InventoryStatusResult:
        """Retrieve stock levels and low-stock indicators for tracked active products."""
        # Query active products joined with their inventory balance
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.code,
                Product.base_unit,
                func.coalesce(InventoryBalance.on_hand_quantity, 0).label("stock"),
            )
            .outerjoin(
                InventoryBalance,
                and_(
                    InventoryBalance.product_id == Product.id,
                    InventoryBalance.organization_id == organization_id,
                ),
            )
            .where(Product.organization_id == organization_id)
            .where(Product.status == "active")
            .order_by(Product.name.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

        items: list[ProductStockItem] = []
        low_stock_count = 0
        out_of_stock_count = 0

        for pid, name, code, unit, stock in rows:
            stock_int = int(stock)
            # Standard P0 reorder threshold = 10 units
            is_out = stock_int <= 0
            is_low = stock_int > 0 and stock_int <= 10

            if is_out:
                out_of_stock_count += 1
            elif is_low:
                low_stock_count += 1

            if low_stock_only and not (is_out or is_low):
                continue

            items.append(
                ProductStockItem(
                    product_id=pid,
                    product_name=name,
                    sku=code,
                    unit=unit,
                    current_stock=stock_int,
                    reorder_point=10,
                    is_low_stock=is_low,
                    is_out_of_stock=is_out,
                )
            )

        return InventoryStatusResult(
            success=True,
            values=InventoryStatusValues(
                total_products_tracked=len(rows),
                low_stock_count=low_stock_count,
                out_of_stock_count=out_of_stock_count,
                items=items,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_inventory_status",
                source_refs=["inventory_balances"],
                caveats=["Standard threshold: 10 units"],
            ),
        )

    @classmethod
    async def get_customer_balance(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        customer_id: UUID | None = None,
        query: str | None = None,
    ) -> CustomerBalanceResult:
        """Calculate recorded order/payment balance for a customer."""
        if not customer_id and not query:
            return CustomerBalanceResult(
                success=False,
                error=ToolError(
                    code=ToolErrorCode.VALIDATION_ERROR,
                    message="Either customer_id or a search query must be provided.",
                ),
                provenance=ProvenanceMeta(source_tool="get_customer_balance"),
            )

        cust_stmt = select(Customer).where(Customer.organization_id == organization_id)
        if customer_id:
            cust_stmt = cust_stmt.where(Customer.id == customer_id)
        elif query:
            search_pattern = f"%{query.strip()}%"
            cust_stmt = cust_stmt.where(
                or_(
                    Customer.name.ilike(search_pattern),
                    Customer.phone.ilike(search_pattern),
                )
            )

        customer = (await session.execute(cust_stmt)).scalars().first()
        if not customer:
            return CustomerBalanceResult(
                success=False,
                error=ToolError(
                    code=ToolErrorCode.NO_MATCHING_DATA,
                    message="No customer matching the specified criteria was found.",
                ),
                provenance=ProvenanceMeta(source_tool="get_customer_balance"),
            )

        # Calculate sum of active orders
        order_stmt = (
            select(
                func.coalesce(func.sum(Order.order_total_minor), 0).label("total_orders"),
                func.count(Order.id).label("order_count"),
            )
            .where(Order.organization_id == organization_id)
            .where(Order.customer_id == customer.id)
            .where(Order.status != "voided")
        )
        orders_total, order_cnt = (await session.execute(order_stmt)).one()

        # Calculate sum of active payments
        pay_stmt = (
            select(
                func.coalesce(func.sum(Payment.amount_minor), 0).label("total_payments"),
                func.count(Payment.id).label("payment_count"),
            )
            .where(Payment.organization_id == organization_id)
            .where(Payment.customer_id == customer.id)
            .where(Payment.status != "voided")
        )
        payments_total, pay_cnt = (await session.execute(pay_stmt)).one()

        balance_minor = int(orders_total) - int(payments_total)

        return CustomerBalanceResult(
            success=True,
            values=CustomerBalanceValues(
                customer_id=customer.id,
                customer_name=customer.name,
                phone=customer.phone,
                total_orders_minor=int(orders_total),
                total_payments_minor=int(payments_total),
                outstanding_balance_minor=balance_minor,
                outstanding_balance_pkr=format_pkr(balance_minor),
                order_count=int(order_cnt),
                payment_count=int(pay_cnt),
            ),
            provenance=ProvenanceMeta(
                source_tool="get_customer_balance",
                source_refs=[f"customer:{customer.id}"],
                caveats=[
                    "Balance is derived from recorded native orders and receipts.",
                    "This is not full accounting reconciliation or verified bank settlement.",
                ],
            ),
        )

    @classmethod
    async def get_order_details(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        order_id: UUID | None = None,
        order_number: str | None = None,
    ) -> OrderDetailsResult:
        """Fetch details of an authorized order and its line items."""
        if not order_id and not order_number:
            return OrderDetailsResult(
                success=False,
                error=ToolError(
                    code=ToolErrorCode.VALIDATION_ERROR,
                    message="Either order_id or order_number must be provided.",
                ),
                provenance=ProvenanceMeta(source_tool="get_order_details"),
            )

        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.organization_id == organization_id)
        )
        if order_id:
            stmt = stmt.where(Order.id == order_id)
        elif order_number:
            stmt = stmt.where(Order.order_number.ilike(order_number.strip()))

        order = (await session.execute(stmt)).scalars().first()
        if not order:
            return OrderDetailsResult(
                success=False,
                error=ToolError(
                    code=ToolErrorCode.NO_MATCHING_DATA,
                    message="Order not found or inaccessible.",
                ),
                provenance=ProvenanceMeta(source_tool="get_order_details"),
            )

        # Resolve optional customer name
        customer_name: str | None = None
        if order.customer_id:
            cust = await session.get(Customer, order.customer_id)
            if cust and cust.organization_id == organization_id:
                customer_name = cust.name

        items = [
            OrderItemDetail(
                product_name=item.product_name_snapshot,
                quantity=item.quantity,
                unit_price_minor=item.unit_price_minor,
                line_total_minor=item.line_total_minor,
            )
            for item in order.items
        ]

        return OrderDetailsResult(
            success=True,
            values=OrderDetailsValues(
                order_id=order.id,
                order_number=order.order_number,
                status=order.status,
                customer_name=customer_name,
                ordered_at=order.ordered_at,
                order_total_minor=order.order_total_minor,
                order_total_pkr=format_pkr(order.order_total_minor),
                items=items,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_order_details",
                source_refs=[f"order:{order.id}"],
            ),
        )

    @classmethod
    async def get_top_products(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        period: DashboardPeriod = DashboardPeriod.THIS_MONTH,
        metric: Literal["quantity", "revenue"] = "revenue",
        limit: int = 5,
    ) -> TopProductsResult:
        """Rank products by quantity sold or revenue within an authorized period."""
        range_info = resolve_period_range(
            period=period,
            tz_name="Asia/Karachi",
        )
        start_utc = range_info.start_utc
        end_utc = range_info.end_utc

        order_col = (
            func.coalesce(func.sum(OrderItem.line_total_minor), 0)
            if metric == "revenue"
            else func.coalesce(func.sum(OrderItem.quantity), 0)
        )

        stmt = (
            select(
                OrderItem.product_id,
                OrderItem.product_name_snapshot,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("qty_sold"),
                func.coalesce(func.sum(OrderItem.line_total_minor), 0).label("revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.organization_id == organization_id)
            .where(Order.status != "voided")
            .where(Order.ordered_at >= start_utc)
            .where(Order.ordered_at < end_utc)
            .group_by(OrderItem.product_id, OrderItem.product_name_snapshot)
            .order_by(desc(order_col))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

        items = [
            TopProductItem(
                product_id=pid,
                product_name=name,
                sku="",
                quantity_sold=int(qty),
                revenue_minor=int(rev),
                revenue_pkr=format_pkr(int(rev)),
            )
            for pid, name, qty, rev in rows
        ]

        return TopProductsResult(
            success=True,
            values=TopProductsValues(
                period=period.value,
                metric=metric,
                items=items,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_top_products",
                period_applied=period.value,
                source_refs=[f"order_items:{period.value}"],
            ),
        )

    @classmethod
    async def get_expense_summary(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        period: DashboardPeriod = DashboardPeriod.TODAY,
        start_date: date | None = None,
        end_date: date | None = None,
        category_id: UUID | None = None,
    ) -> ExpenseSummaryResult:
        """Calculate total operating expenses and category breakdown."""
        range_info = resolve_period_range(
            period=period,
            tz_name="Asia/Karachi",
            custom_start_date=start_date,
            custom_end_date=end_date,
        )
        start_utc = range_info.start_utc
        end_utc = range_info.end_utc

        base_filter = [
            Expense.organization_id == organization_id,
            Expense.status != "voided",
            Expense.occurred_at >= start_utc,
            Expense.occurred_at < end_utc,
        ]
        if category_id:
            base_filter.append(Expense.expense_category_id == category_id)

        # Aggregate total
        total_stmt = (
            select(
                func.coalesce(func.sum(Expense.amount_minor), 0),
                func.count(Expense.id),
            ).where(and_(*base_filter))
        )
        total_exp, count = (await session.execute(total_stmt)).one()

        # Breakdown by category
        cat_stmt = (
            select(
                ExpenseCategory.id,
                ExpenseCategory.name,
                func.coalesce(func.sum(Expense.amount_minor), 0).label("cat_total"),
                func.count(Expense.id).label("cat_count"),
            )
            .join(ExpenseCategory, ExpenseCategory.id == Expense.expense_category_id)
            .where(and_(*base_filter))
            .group_by(ExpenseCategory.id, ExpenseCategory.name)
            .order_by(desc("cat_total"))
        )
        cat_rows = (await session.execute(cat_stmt)).all()

        categories = [
            ExpenseCategoryBreakdown(
                category_id=cid,
                category_name=cname,
                total_minor=int(ctot),
                total_pkr=format_pkr(int(ctot)),
                count=int(ccnt),
            )
            for cid, cname, ctot, ccnt in cat_rows
        ]

        return ExpenseSummaryResult(
            success=True,
            values=ExpenseSummaryValues(
                total_expenses_minor=int(total_exp),
                total_expenses_pkr=format_pkr(int(total_exp)),
                expense_count=int(count),
                period=period.value,
                categories=categories,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_expense_summary",
                period_applied=period.value,
                source_refs=[f"expenses:{period.value}"],
                caveats=["Excludes voided expenses"],
            ),
        )

    @classmethod
    async def get_payment_summary(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        period: DashboardPeriod = DashboardPeriod.TODAY,
        start_date: date | None = None,
        end_date: date | None = None,
        channel: str | None = None,
    ) -> PaymentSummaryResult:
        """Calculate recorded payment totals and payment channel breakdown."""
        range_info = resolve_period_range(
            period=period,
            tz_name="Asia/Karachi",
            custom_start_date=start_date,
            custom_end_date=end_date,
        )
        start_utc = range_info.start_utc
        end_utc = range_info.end_utc

        base_filter = [
            Payment.organization_id == organization_id,
            Payment.status != "voided",
            Payment.received_at >= start_utc,
            Payment.received_at < end_utc,
        ]
        if channel:
            base_filter.append(Payment.channel == channel)

        total_stmt = (
            select(
                func.coalesce(func.sum(Payment.amount_minor), 0),
                func.count(Payment.id),
            ).where(and_(*base_filter))
        )
        total_pay, count = (await session.execute(total_stmt)).one()

        chan_stmt = (
            select(
                Payment.channel,
                func.coalesce(func.sum(Payment.amount_minor), 0).label("chan_total"),
                func.count(Payment.id).label("chan_count"),
            )
            .where(and_(*base_filter))
            .group_by(Payment.channel)
            .order_by(desc("chan_total"))
        )
        chan_rows = (await session.execute(chan_stmt)).all()

        channels = [
            PaymentChannelBreakdown(
                channel=ch,
                total_minor=int(ctot),
                total_pkr=format_pkr(int(ctot)),
                count=int(ccnt),
            )
            for ch, ctot, ccnt in chan_rows
        ]

        return PaymentSummaryResult(
            success=True,
            values=PaymentSummaryValues(
                total_payments_minor=int(total_pay),
                total_payments_pkr=format_pkr(int(total_pay)),
                payment_count=int(count),
                period=period.value,
                channels=channels,
            ),
            provenance=ProvenanceMeta(
                source_tool="get_payment_summary",
                period_applied=period.value,
                source_refs=[f"payments:{period.value}"],
                caveats=[
                    "Excludes voided receipts.",
                    "Represents internal business receipts, not bank settlement.",
                ],
            ),
        )

    @classmethod
    async def get_dashboard_summary(
        cls,
        session: AsyncSession,
        organization_id: UUID,
        period: DashboardPeriod = DashboardPeriod.TODAY,
        start_date: date | None = None,
        end_date: date | None = None,
        role: MemberRole = MemberRole.OWNER,
    ) -> DashboardSummaryResult:
        """Return the exact same deterministic values as the P0 operational dashboard."""
        dto = await DashboardQueryService.get_dashboard_summary(
            session=session,
            organization_id=organization_id,
            period=period,
            start_date=start_date,
            end_date=end_date,
            caller_role=role,
        )

        return DashboardSummaryResult(
            success=True,
            values=dto.model_dump(mode="json"),
            provenance=ProvenanceMeta(
                source_tool="get_dashboard_summary",
                period_applied=period.value,
                source_refs=[f"dashboard:{organization_id}:{period.value}"],
                caveats=["Role-aware operational summary"],
            ),
        )

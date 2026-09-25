"""Deterministic dashboard query service (DASH-001)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.schemas import (
    DashboardFreshnessDTO,
    DashboardSummaryDTO,
    ExpensesSummaryDTO,
    InventorySummaryDTO,
    LowStockItemDTO,
    NetCashSummaryDTO,
    PaymentsSummaryDTO,
    RecentActivityItemDTO,
    SalesSummaryDTO,
)
from app.modules.dashboard.timezone import (
    DEFAULT_TIMEZONE,
    DashboardPeriod,
    resolve_period_range,
)
from app.modules.expenses.models import Expense
from app.modules.inventory.models import InventoryBalance
from app.modules.orders.models import Order
from app.modules.organizations.models import Organization
from app.modules.organizations.permissions import Permission, has_permission
from app.modules.payments.models import Payment
from app.modules.products.models import Product


class DashboardQueryService:
    """Service executing deterministic operational aggregations within tenant boundaries."""

    @staticmethod
    async def get_dashboard_summary(
        session: AsyncSession,
        organization_id: uuid.UUID,
        caller_role: str,
        period: str | DashboardPeriod = DashboardPeriod.TODAY,
        start_date: date | None = None,
        end_date: date | None = None,
        low_stock_threshold: int = 10,
        reference_utc: datetime | None = None,
    ) -> DashboardSummaryDTO:
        """Calculate basic operational metrics strictly scoped to organization_id."""
        # 1. Fetch organization timezone and currency
        org_stmt = select(Organization.timezone, Organization.currency_code).where(
            Organization.id == organization_id
        )
        org_res = await session.execute(org_stmt)
        org_row = org_res.first()
        tz_name = org_row[0] if org_row and org_row[0] else DEFAULT_TIMEZONE
        currency_code = org_row[1] if org_row and org_row[1] else "PKR"

        # 2. Resolve query time boundaries in UTC
        period_range = resolve_period_range(
            period=period,
            tz_name=tz_name,
            custom_start_date=start_date,
            custom_end_date=end_date,
            reference_utc=reference_utc,
        )

        now_utc = reference_utc or datetime.now(timezone.utc)

        # 3. Query sales (orders)
        orders_stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.order_total_minor), 0),
        ).where(
            Order.organization_id == organization_id,
            Order.status == "active",
            Order.ordered_at >= period_range.start_utc,
            Order.ordered_at <= period_range.end_utc,
        )
        orders_res = await session.execute(orders_stmt)
        order_count, total_sales_minor = orders_res.one()

        sales_summary = SalesSummaryDTO(
            order_count=int(order_count or 0),
            total_sales_minor=int(total_sales_minor or 0),
            currency_code=currency_code,
        )

        # 4. Query payments
        payments_stmt = select(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount_minor), 0),
        ).where(
            Payment.organization_id == organization_id,
            Payment.status == "active",
            Payment.received_at >= period_range.start_utc,
            Payment.received_at <= period_range.end_utc,
        )
        payments_res = await session.execute(payments_stmt)
        payment_count, total_collected_minor = payments_res.one()

        payments_summary = PaymentsSummaryDTO(
            payment_count=int(payment_count or 0),
            total_collected_minor=int(total_collected_minor or 0),
            currency_code=currency_code,
        )

        # 5. Role-based expense visibility
        can_read_expenses = has_permission(
            caller_role, Permission.EXPENSES_READ
        ) and has_permission(caller_role, Permission.DASHBOARD_READ_OPERATIONAL)

        expenses_summary: ExpensesSummaryDTO | None = None
        net_cash_summary: NetCashSummaryDTO | None = None

        if can_read_expenses:
            expenses_stmt = select(
                func.count(Expense.id),
                func.coalesce(func.sum(Expense.amount_minor), 0),
            ).where(
                Expense.organization_id == organization_id,
                Expense.status == "active",
                Expense.occurred_at >= period_range.start_utc,
                Expense.occurred_at <= period_range.end_utc,
            )
            expenses_res = await session.execute(expenses_stmt)
            expense_count, total_expenses_minor = expenses_res.one()

            expenses_summary = ExpensesSummaryDTO(
                expense_count=int(expense_count or 0),
                total_expenses_minor=int(total_expenses_minor or 0),
                currency_code=currency_code,
            )

            net_cash_minor = int(total_collected_minor or 0) - int(total_expenses_minor or 0)
            net_cash_summary = NetCashSummaryDTO(
                net_cash_minor=net_cash_minor,
                currency_code=currency_code,
            )

        # 6. Inventory low-stock indicators
        inventory_stmt = (
            select(
                Product.id,
                Product.code,
                Product.name,
                Product.base_unit,
                InventoryBalance.on_hand_quantity,
            )
            .join(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(
                Product.organization_id == organization_id,
                Product.status == "active",
                InventoryBalance.organization_id == organization_id,
                InventoryBalance.on_hand_quantity <= low_stock_threshold,
            )
            .order_by(InventoryBalance.on_hand_quantity.asc(), Product.name.asc())
            .limit(20)
        )
        inv_res = await session.execute(inventory_stmt)
        inv_rows = inv_res.all()

        low_stock_items = [
            LowStockItemDTO(
                product_id=row.id,
                product_code=row.code,
                product_name=row.name,
                base_unit=row.base_unit,
                on_hand_quantity=row.on_hand_quantity,
                is_out_of_stock=(row.on_hand_quantity <= 0),
            )
            for row in inv_rows
        ]

        # Total count of low stock items across entire inventory
        low_stock_count_stmt = (
            select(func.count(Product.id))
            .join(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(
                Product.organization_id == organization_id,
                Product.status == "active",
                InventoryBalance.organization_id == organization_id,
                InventoryBalance.on_hand_quantity <= low_stock_threshold,
            )
        )
        low_stock_count_res = await session.execute(low_stock_count_stmt)
        total_low_stock = low_stock_count_res.scalar() or 0

        inventory_summary = InventorySummaryDTO(
            low_stock_count=int(total_low_stock),
            low_stock_threshold=low_stock_threshold,
            items=low_stock_items,
        )

        # 7. Recent activity (role-filtered)
        recent_activities: list[RecentActivityItemDTO] = []

        # Recent orders (Staff, Manager, Owner)
        recent_orders_stmt = (
            select(
                Order.id,
                Order.order_number,
                Order.order_total_minor,
                Order.ordered_at,
                Order.status,
            )
            .where(
                Order.organization_id == organization_id,
                Order.status == "active",
            )
            .order_by(Order.ordered_at.desc())
            .limit(10)
        )
        orders_activity_res = await session.execute(recent_orders_stmt)
        for row in orders_activity_res.all():
            recent_activities.append(
                RecentActivityItemDTO(
                    id=row.id,
                    activity_type="order",
                    reference_code=row.order_number,
                    amount_minor=row.order_total_minor,
                    currency_code=currency_code,
                    timestamp=row.ordered_at,
                    status=row.status,
                    description=f"Sales order {row.order_number}",
                )
            )

        # Recent payments (Staff, Manager, Owner)
        recent_payments_stmt = (
            select(
                Payment.id,
                Payment.amount_minor,
                Payment.received_at,
                Payment.status,
                Payment.channel,
                Payment.external_reference,
                Payment.account_label,
            )
            .where(
                Payment.organization_id == organization_id,
                Payment.status == "active",
            )
            .order_by(Payment.received_at.desc())
            .limit(10)
        )
        payments_activity_res = await session.execute(recent_payments_stmt)
        for row in payments_activity_res.all():
            ref_code = row.external_reference or row.account_label or f"PAY-{str(row.id)[:8]}"
            recent_activities.append(
                RecentActivityItemDTO(
                    id=row.id,
                    activity_type="payment",
                    reference_code=ref_code,
                    amount_minor=row.amount_minor,
                    currency_code=currency_code,
                    timestamp=row.received_at,
                    status=row.status,
                    description=f"Payment received ({row.channel})",
                )
            )

        # Recent expenses (Manager, Owner ONLY)
        if can_read_expenses:
            recent_expenses_stmt = (
                select(
                    Expense.id,
                    Expense.payee,
                    Expense.amount_minor,
                    Expense.occurred_at,
                    Expense.status,
                    Expense.description,
                )
                .where(
                    Expense.organization_id == organization_id,
                    Expense.status == "active",
                )
                .order_by(Expense.occurred_at.desc())
                .limit(10)
            )
            expenses_activity_res = await session.execute(recent_expenses_stmt)
            for row in expenses_activity_res.all():
                ref_label = row.payee or "General Expense"
                recent_activities.append(
                    RecentActivityItemDTO(
                        id=row.id,
                        activity_type="expense",
                        reference_code=ref_label,
                        amount_minor=row.amount_minor,
                        currency_code=currency_code,
                        timestamp=row.occurred_at,
                        status=row.status,
                        description=row.description or f"Expense for {ref_label}",
                    )
                )

        # Sort combined activity by timestamp desc and take top 15
        recent_activities.sort(key=lambda x: x.timestamp, reverse=True)
        recent_activities = recent_activities[:15]

        # 8. Assemble freshness metadata
        freshness = DashboardFreshnessDTO(
            generated_at=now_utc,
            period=period_range.period,
            local_start_date=period_range.local_start_date.isoformat(),
            local_end_date=period_range.local_end_date.isoformat(),
            timezone=period_range.timezone_name,
        )

        return DashboardSummaryDTO(
            sales=sales_summary,
            payments=payments_summary,
            expenses=expenses_summary,
            net_cash=net_cash_summary,
            inventory=inventory_summary,
            recent_activity=recent_activities,
            freshness=freshness,
        )

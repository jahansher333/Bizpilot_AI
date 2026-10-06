"""Read-only customer order/payment balances (R5 customer list and detail).

Counts only ``active`` orders and payments, matching the dashboard: voided records and
corrected originals are excluded so a correction is never counted twice. This is a
derived view of recorded receipts, not an accounting ledger or bank reconciliation.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.schemas import CustomerBalanceItemSchema, CustomerBalancesResponseSchema
from app.modules.orders.models import Order
from app.modules.organizations.models import Organization
from app.modules.payments.models import Payment


async def get_customer_balances(
    session: AsyncSession,
    organization_id: uuid.UUID,
    customer_id: Optional[uuid.UUID] = None,
) -> CustomerBalancesResponseSchema:
    order_active = Order.status == "active"
    orders_stmt = (
        select(
            Order.customer_id,
            func.count(Order.id).filter(order_active).label("order_count"),
            func.coalesce(func.sum(Order.order_total_minor).filter(order_active), 0).label("orders_total"),
            func.count(Order.id).filter(Order.status == "voided").label("voided_count"),
        )
        .where(Order.organization_id == organization_id, Order.customer_id.is_not(None))
        .group_by(Order.customer_id)
    )
    payments_stmt = (
        select(
            Payment.customer_id,
            func.count(Payment.id).label("payment_count"),
            func.coalesce(func.sum(Payment.amount_minor), 0).label("payments_total"),
        )
        .where(
            Payment.organization_id == organization_id,
            Payment.customer_id.is_not(None),
            Payment.status == "active",
        )
        .group_by(Payment.customer_id)
    )
    if customer_id is not None:
        orders_stmt = orders_stmt.where(Order.customer_id == customer_id)
        payments_stmt = payments_stmt.where(Payment.customer_id == customer_id)

    totals: dict[uuid.UUID, dict[str, int]] = {}

    def entry(cid: uuid.UUID) -> dict[str, int]:
        return totals.setdefault(cid, {"order_count": 0, "voided": 0, "orders": 0, "payment_count": 0, "payments": 0})

    for cid, order_count, orders_total, voided_count in (await session.execute(orders_stmt)).all():
        e = entry(cid)
        e["order_count"] = int(order_count)
        e["orders"] = int(orders_total)
        e["voided"] = int(voided_count)
    for cid, payment_count, payments_total in (await session.execute(payments_stmt)).all():
        e = entry(cid)
        e["payment_count"] = int(payment_count)
        e["payments"] = int(payments_total)

    items = [
        CustomerBalanceItemSchema(
            customer_id=cid,
            order_count=e["order_count"],
            voided_order_count=e["voided"],
            total_orders_minor=e["orders"],
            payment_count=e["payment_count"],
            total_payments_minor=e["payments"],
            balance_minor=e["orders"] - e["payments"],
        )
        for cid, e in totals.items()
    ]
    if customer_id is not None and not items:
        items = [
            CustomerBalanceItemSchema(
                customer_id=customer_id,
                order_count=0,
                voided_order_count=0,
                total_orders_minor=0,
                payment_count=0,
                total_payments_minor=0,
                balance_minor=0,
            )
        ]

    currency = (
        await session.execute(select(Organization.currency_code).where(Organization.id == organization_id))
    ).scalar_one_or_none() or "PKR"

    owing = [i for i in items if i.balance_minor > 0]
    return CustomerBalancesResponseSchema(
        currency_code=currency,
        items=items,
        customers_with_orders=sum(1 for i in items if i.order_count > 0),
        customers_with_balance=len(owing),
        outstanding_minor=sum(i.balance_minor for i in owing),
    )

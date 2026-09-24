"""Tenant-scoped data access repository for payments (PAY-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationException
from app.db.repositories import ScopedRepository
from app.modules.customers.models import Customer
from app.modules.orders.models import Order
from app.modules.payments.models import Payment


class PaymentRepository(ScopedRepository[Payment]):
    """Repository strictly scoping payment queries and persistence to an organization tenant."""

    model_cls = Payment

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, Payment)

    async def create_payment(
        self,
        amount_minor: int,
        channel: str,
        currency_code: str = "PKR",
        customer_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        received_at: Optional[datetime] = None,
        account_label: Optional[str] = None,
        external_reference: Optional[str] = None,
        notes: Optional[str] = None,
        created_by_user_id: Optional[uuid.UUID] = None,
        status: str = "active",
        corrects_payment_id: Optional[uuid.UUID] = None,
        replaced_by_payment_id: Optional[uuid.UUID] = None,
    ) -> Payment:
        """Persist a new tenant-scoped payment receipt.

        Enforces tenant relationship consistency for optional customer and order.
        """
        # Validate customer relationship tenant consistency
        if customer_id is not None:
            cust_stmt = select(Customer.id).where(
                Customer.id == customer_id,
                Customer.organization_id == self._organization_id,
            )
            cust_res = await self._session.execute(cust_stmt)
            if cust_res.scalar_one_or_none() is None:
                raise ValidationException("Referenced customer does not exist in this organization")

        # Validate order relationship tenant consistency
        if order_id is not None:
            ord_stmt = select(Order.id).where(
                Order.id == order_id,
                Order.organization_id == self._organization_id,
            )
            ord_res = await self._session.execute(ord_stmt)
            if ord_res.scalar_one_or_none() is None:
                raise ValidationException("Referenced order does not exist in this organization")

        rec_at = received_at or datetime.now(timezone.utc)

        payment = Payment(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            customer_id=customer_id,
            order_id=order_id,
            amount_minor=amount_minor,
            currency_code=currency_code,
            received_at=rec_at,
            channel=channel,
            account_label=account_label,
            external_reference=external_reference,
            notes=notes,
            status=status,
            created_by_user_id=created_by_user_id,
            corrects_payment_id=corrects_payment_id,
            replaced_by_payment_id=replaced_by_payment_id,
        )
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_external_reference(self, external_reference: str) -> Optional[Payment]:
        """Fetch active payment matching external reference within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(Payment.external_reference == external_reference)
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_payments(
        self,
        customer_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Payment], int]:
        """List payments within bound tenant with optional filters and pagination."""
        base_where = [Payment.organization_id == self._organization_id]
        if customer_id is not None:
            base_where.append(Payment.customer_id == customer_id)
        if order_id is not None:
            base_where.append(Payment.order_id == order_id)
        if status is not None:
            base_where.append(Payment.status == status)
        if channel is not None:
            base_where.append(Payment.channel == channel)

        count_stmt = select(func.count(Payment.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(Payment)
            .where(*base_where)
            .order_by(Payment.received_at.desc(), Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        return items_res.scalars().all(), total

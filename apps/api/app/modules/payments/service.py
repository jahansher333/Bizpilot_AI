"""Application domain service for recording and querying business payments (PAY-002)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.models import Customer
from app.modules.orders.models import Order
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.payments.enums import PaymentChannel, PaymentStatus
from app.modules.payments.models import Payment
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import PaymentCreate


class PaymentService:
    """Domain service managing payment recording, querying, and tenant integrity."""

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id
        self._repo = PaymentRepository(session, organization_id)

    async def record_payment(
        self,
        payment_in: PaymentCreate,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> Payment:
        """Record a business payment receipt.

        Enforces RBAC, positive integer amount, duplicate-reference rejection,
        and tenant-safe optional associations.
        """
        check_permission(actor_role, Permission.PAYMENTS_CREATE)

        if payment_in.amount_minor <= 0:
            raise ValidationException("Payment amount must be greater than zero")

        if len(payment_in.currency_code) != 3:
            raise ValidationException("Currency code must be exactly 3 characters")

        # Check duplicate external reference within organization
        if payment_in.external_reference and payment_in.external_reference.strip():
            ref_clean = payment_in.external_reference.strip()
            existing = await self._repo.get_by_external_reference(ref_clean)
            if existing is not None and existing.status == PaymentStatus.ACTIVE.value:
                raise ValidationException(
                    f"Payment with external reference '{ref_clean}' already exists in this organization"
                )
            ext_ref = ref_clean
        else:
            ext_ref = None

        # Tenant-safe customer validation
        if payment_in.customer_id is not None:
            cust_stmt = select(Customer.id).where(
                Customer.id == payment_in.customer_id,
                Customer.organization_id == self._organization_id,
            )
            cust_res = await self._session.execute(cust_stmt)
            if cust_res.scalar_one_or_none() is None:
                raise ValidationException("Referenced customer does not exist in this organization")

        # Tenant-safe order validation
        if payment_in.order_id is not None:
            ord_stmt = select(Order).where(
                Order.id == payment_in.order_id,
                Order.organization_id == self._organization_id,
            )
            ord_res = await self._session.execute(ord_stmt)
            order = ord_res.scalar_one_or_none()
            if order is None:
                raise ValidationException("Referenced order does not exist in this organization")
            if order.status == "voided":
                raise ValidationException("Cannot record payment against a voided order")

        received_at = payment_in.received_at or datetime.now(timezone.utc)

        payment = await self._repo.create_payment(
            amount_minor=payment_in.amount_minor,
            channel=payment_in.channel.value,
            currency_code=payment_in.currency_code,
            customer_id=payment_in.customer_id,
            order_id=payment_in.order_id,
            received_at=received_at,
            account_label=payment_in.account_label.strip() if payment_in.account_label else None,
            external_reference=ext_ref,
            notes=payment_in.notes.strip() if payment_in.notes else None,
            created_by_user_id=actor_user_id,
            status=PaymentStatus.ACTIVE.value,
        )
        return payment

    async def get_payment(
        self,
        payment_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> Payment:
        """Fetch payment by ID ensuring RBAC and tenant isolation."""
        check_permission(actor_role, Permission.PAYMENTS_READ)

        stmt = (
            self._repo.scoped_query()
            .where(Payment.id == payment_id)
            .limit(1)
        )
        res = await self._session.execute(stmt)
        payment = res.scalar_one_or_none()
        if payment is None:
            raise NotFoundException("Payment not found")
        return payment

    async def list_payments(
        self,
        actor_role: str | MemberRole,
        customer_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Payment], int]:
        """List payments with optional filters and pagination."""
        check_permission(actor_role, Permission.PAYMENTS_READ)
        return await self._repo.list_payments(
            customer_id=customer_id,
            order_id=order_id,
            status=status,
            channel=channel,
            limit=limit,
            offset=offset,
        )

    async def get_daily_payment_total(
        self,
        target_date: date,
        actor_role: str | MemberRole,
    ) -> int:
        """Compute sum of active payment amounts received on a given date (UTC)."""
        check_permission(actor_role, Permission.PAYMENTS_READ)

        start_dt = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        stmt = select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
            Payment.organization_id == self._organization_id,
            Payment.status == PaymentStatus.ACTIVE.value,
            Payment.received_at >= start_dt,
            Payment.received_at <= end_dt,
        )
        res = await self._session.execute(stmt)
        return int(res.scalar_one())

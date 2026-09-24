"""Application domain service for recording, idempotency, void, and correction of payments (PAY-002, PAY-003)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.models import Customer
from app.modules.idempotency.service import IdempotencyService, compute_request_hash
from app.modules.orders.models import Order
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.payments.enums import PaymentChannel, PaymentStatus
from app.modules.payments.models import Payment
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    PaymentCorrectionRequest,
    PaymentCreate,
    PaymentResponse,
    PaymentVoidRequest,
)
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.service import InternalTraceService


class PaymentService:
    """Domain service managing payment recording, querying, idempotency, void, and correction."""

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        idempotency_service: Optional[IdempotencyService] = None,
        trace_service: Optional[InternalTraceService] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._repo = PaymentRepository(session, organization_id)
        self._idempotency_service = idempotency_service or IdempotencyService(session)
        self._trace_service = trace_service or InternalTraceService(session, organization_id)

    async def record_payment(
        self,
        payment_in: PaymentCreate,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
        idempotency_key: Optional[str] = None,
    ) -> Payment:
        """Record a business payment receipt.

        Enforces RBAC, positive integer amount, duplicate-reference rejection,
        tenant-safe optional associations, and retry-safe idempotency.
        """
        check_permission(actor_role, Permission.PAYMENTS_CREATE)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            req_hash = compute_request_hash(payment_in)
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="payment:record",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                # Replay existing payment
                resp = PaymentResponse.model_validate_json(payload_str)
                stmt = select(Payment).where(
                    Payment.id == resp.id,
                    Payment.organization_id == self._organization_id,
                )
                existing = await self._session.scalar(stmt)
                if existing is not None:
                    return existing

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

        if clean_key and req_hash:
            resp_dto = PaymentResponse.model_validate(payment)
            await self._idempotency_service.record_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="payment:record",
                idempotency_key=clean_key,
                request_hash=req_hash,
                response_code=201,
                response_payload=resp_dto.model_dump_json(),
            )

        return payment

    async def void_payment(
        self,
        payment_id: uuid.UUID,
        void_data: PaymentVoidRequest,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> Payment:
        """Void an active payment receipt (Owner only).

        Preserves immutable financial history, emits a finance trace event,
        and marks payment voided.
        """
        check_permission(actor_role, Permission.PAYMENTS_VOID)

        payment = await self.get_payment(payment_id, actor_role)

        if payment.status == PaymentStatus.VOIDED.value:
            raise ValidationException("Payment is already voided")
        if payment.status == PaymentStatus.CORRECTED.value:
            raise ValidationException("Cannot void a payment that has already been corrected")

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.VOIDED.value
        payment.voided_at = now
        reason_clean = void_data.reason.strip()
        current_notes = payment.notes or ""
        payment.notes = f"[VOIDED: {reason_clean}] {current_notes}".strip()
        self._session.add(payment)
        await self._session.flush()

        await self._trace_service.record_event(
            action=TraceAction.FINANCE_RECORD_VOIDED,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="payment",
            target_id=payment.id,
            metadata={
                "payment_id": str(payment.id),
                "amount_minor": payment.amount_minor,
                "currency_code": payment.currency_code,
                "void_reason": reason_clean,
            },
        )
        await self._session.flush()
        return payment

    async def correct_payment(
        self,
        payment_id: uuid.UUID,
        correction_data: PaymentCorrectionRequest,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> Payment:
        """Correct an active payment by issuing an auditable replacement (Owner and Manager).

        Marks original as 'corrected', links 'corrects_payment_id' and
        'replaced_by_payment_id', and emits a finance trace event.
        """
        check_permission(actor_role, Permission.PAYMENTS_CORRECT)

        original = await self.get_payment(payment_id, actor_role)

        if original.status == PaymentStatus.VOIDED.value:
            raise ValidationException("Cannot correct a voided payment")
        if original.status == PaymentStatus.CORRECTED.value:
            raise ValidationException("Payment has already been corrected")

        # Determine effective replacement parameters
        new_amount = correction_data.amount_minor if correction_data.amount_minor is not None else original.amount_minor
        if new_amount <= 0:
            raise ValidationException("Payment amount must be greater than zero")

        new_channel = correction_data.channel.value if correction_data.channel is not None else original.channel
        new_customer_id = correction_data.customer_id if correction_data.customer_id is not None else original.customer_id
        new_order_id = correction_data.order_id if correction_data.order_id is not None else original.order_id
        new_account_label = correction_data.account_label.strip() if correction_data.account_label is not None else original.account_label
        new_ext_ref = correction_data.external_reference.strip() if correction_data.external_reference is not None else original.external_reference

        # Check duplicate external reference if changed
        if new_ext_ref and new_ext_ref != original.external_reference:
            existing = await self._repo.get_by_external_reference(new_ext_ref)
            if existing is not None and existing.id != original.id and existing.status == PaymentStatus.ACTIVE.value:
                raise ValidationException(
                    f"Payment with external reference '{new_ext_ref}' already exists in this organization"
                )

        reason_clean = correction_data.reason.strip()
        custom_notes = correction_data.notes.strip() if correction_data.notes else (original.notes or "")
        combined_notes = f"[CORRECTION: {reason_clean}] {custom_notes}".strip()

        # Create replacement payment
        replacement = await self._repo.create_payment(
            amount_minor=new_amount,
            channel=new_channel,
            currency_code=original.currency_code,
            customer_id=new_customer_id,
            order_id=new_order_id,
            received_at=original.received_at,
            account_label=new_account_label,
            external_reference=new_ext_ref,
            notes=combined_notes,
            created_by_user_id=actor_user_id,
            status=PaymentStatus.ACTIVE.value,
            corrects_payment_id=original.id,
        )

        # Update original payment
        original.status = PaymentStatus.CORRECTED.value
        original.replaced_by_payment_id = replacement.id
        self._session.add(original)
        await self._session.flush()

        await self._trace_service.record_event(
            action=TraceAction.FINANCE_RECORD_CORRECTED,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="payment",
            target_id=original.id,
            metadata={
                "original_payment_id": str(original.id),
                "replacement_payment_id": str(replacement.id),
                "correction_reason": reason_clean,
                "original_amount_minor": original.amount_minor,
                "replacement_amount_minor": replacement.amount_minor,
            },
        )
        await self._session.flush()
        return replacement

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

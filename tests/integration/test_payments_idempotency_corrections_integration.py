"""Integration tests for Payment Idempotency, Void, and Correction (PAY-003)."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.orders.models import Order
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.payments.enums import PaymentChannel, PaymentStatus
from app.modules.payments.models import Payment
from app.modules.payments.schemas import (
    PaymentCorrectionRequest,
    PaymentCreate,
    PaymentVoidRequest,
)
from app.modules.payments.service import PaymentService
from app.modules.trace.enums import TraceAction
from app.modules.trace.models import InternalTraceEvent
from app.modules.auth.models import User


async def _create_test_org(db_session: AsyncSession, name: str = "Pay Idemp Org") -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        display_name=name,
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()
    return org


async def _create_test_user(db_session: AsyncSession, prefix: str = "pay_idem_user") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Idem Payer",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_payment_idempotency_safe_replay(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Idemp Replay Org")
    user = await _create_test_user(db_session, "user1")
    await db_session.commit()
    service = PaymentService(db_session, org.id)

    key = "idem-pay-key-001"
    payload = PaymentCreate(
        amount_minor=50000,
        channel=PaymentChannel.BANK_TRANSFER,
        account_label="Standard Chartered",
        external_reference="IBFT-112233",
        notes="Invoice payment",
    )

    # First attempt: records payment
    p1 = await service.record_payment(payload, user.id, MemberRole.STAFF, idempotency_key=key)
    await db_session.commit()
    assert p1.id is not None
    assert p1.amount_minor == 50000

    # Second attempt: exact same key and payload returns cached payment
    p2 = await service.record_payment(payload, user.id, MemberRole.STAFF, idempotency_key=key)
    await db_session.commit()
    assert p2.id == p1.id

    # Verify database only contains 1 payment row
    stmt = select(Payment).where(Payment.organization_id == org.id)
    res = await db_session.execute(stmt)
    payments = res.scalars().all()
    assert len(payments) == 1


@pytest.mark.asyncio
async def test_payment_idempotency_conflict_rejection(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Idemp Conflict Org")
    user = await _create_test_user(db_session, "user2")
    await db_session.commit()
    service = PaymentService(db_session, org.id)

    key = "idem-pay-conflict-key"
    payload1 = PaymentCreate(
        amount_minor=10000,
        channel=PaymentChannel.CASH,
    )
    p1 = await service.record_payment(payload1, user.id, MemberRole.STAFF, idempotency_key=key)
    await db_session.commit()
    assert p1.id is not None

    # Reusing same key with changed payload raises ConflictException (409 Conflict)
    payload2 = PaymentCreate(
        amount_minor=20000,  # Changed amount
        channel=PaymentChannel.CASH,
    )
    with pytest.raises(ConflictException, match="previously used with different parameters"):
        await service.record_payment(payload2, user.id, MemberRole.STAFF, idempotency_key=key)


@pytest.mark.asyncio
async def test_payment_void_lifecycle_and_rbac(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Void Org")
    user_owner = await _create_test_user(db_session, "owner")
    user_mgr = await _create_test_user(db_session, "mgr")
    user_staff = await _create_test_user(db_session, "staff")
    service = PaymentService(db_session, org.id)

    # Record payment
    payment = await service.record_payment(
        PaymentCreate(amount_minor=35000, channel=PaymentChannel.CASH),
        user_staff.id,
        MemberRole.STAFF,
    )
    assert payment.status == PaymentStatus.ACTIVE.value

    # 1. Staff void attempt DENIED with 403
    with pytest.raises(AuthorizationException):
        await service.void_payment(payment.id, PaymentVoidRequest(reason="Mistake"), user_staff.id, MemberRole.STAFF)

    # 2. Manager void attempt DENIED with 403 (Owner only)
    with pytest.raises(AuthorizationException):
        await service.void_payment(payment.id, PaymentVoidRequest(reason="Mistake"), user_mgr.id, MemberRole.MANAGER)

    # 3. Owner void attempt SUCCEEDS
    voided = await service.void_payment(
        payment.id,
        PaymentVoidRequest(reason="Customer returned goods and payment cancelled"),
        user_owner.id,
        MemberRole.OWNER,
    )
    assert voided.status == PaymentStatus.VOIDED.value
    assert voided.voided_at is not None
    assert "[VOIDED: Customer returned goods and payment cancelled]" in voided.notes

    # 4. Verify trace event generated
    trace_stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.organization_id == org.id,
        InternalTraceEvent.target_id == payment.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_VOIDED.value,
    )
    trace_res = await db_session.execute(trace_stmt)
    event = trace_res.scalar_one()
    assert event.target_type == "payment"
    assert event.actor_user_id == user_owner.id

    # 5. Voiding an already voided payment raises ValidationException
    with pytest.raises(ValidationException, match="already voided"):
        await service.void_payment(
            payment.id,
            PaymentVoidRequest(reason="Repeat void"),
            user_owner.id,
            MemberRole.OWNER,
        )


@pytest.mark.asyncio
async def test_payment_correction_lifecycle_and_rbac(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Correction Org")
    user_owner = await _create_test_user(db_session, "corr_owner")
    user_mgr = await _create_test_user(db_session, "corr_mgr")
    user_staff = await _create_test_user(db_session, "corr_staff")
    service = PaymentService(db_session, org.id)

    # Record payment
    original = await service.record_payment(
        PaymentCreate(
            amount_minor=40000,
            channel=PaymentChannel.CASH,
            account_label="Old Drawer",
            external_reference="ORIG-111",
            notes="Initial payment",
        ),
        user_staff.id,
        MemberRole.STAFF,
    )
    assert original.status == PaymentStatus.ACTIVE.value

    # 1. Staff correction attempt DENIED with 403
    with pytest.raises(AuthorizationException):
        await service.correct_payment(
            original.id,
            PaymentCorrectionRequest(amount_minor=45000, reason="Typo in amount"),
            user_staff.id,
            MemberRole.STAFF,
        )

    # 2. Manager correction attempt SUCCEEDS
    replacement = await service.correct_payment(
        original.id,
        PaymentCorrectionRequest(
            amount_minor=45000,
            channel=PaymentChannel.BANK_TRANSFER,
            account_label="Habib Bank",
            external_reference="CORR-222",
            reason="Corrected amount from 40k to 45k and channel to bank",
        ),
        user_mgr.id,
        MemberRole.MANAGER,
    )

    # Verify replacement payment
    assert replacement.id is not None
    assert replacement.id != original.id
    assert replacement.amount_minor == 45000
    assert replacement.channel == "bank_transfer"
    assert replacement.account_label == "Habib Bank"
    assert replacement.external_reference == "CORR-222"
    assert replacement.status == PaymentStatus.ACTIVE.value
    assert replacement.corrects_payment_id == original.id

    # Verify original payment updated
    loaded_orig = await service.get_payment(original.id, MemberRole.MANAGER)
    assert loaded_orig.status == PaymentStatus.CORRECTED.value
    assert loaded_orig.replaced_by_payment_id == replacement.id

    # Verify trace event for correction
    trace_stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.organization_id == org.id,
        InternalTraceEvent.target_id == original.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_CORRECTED.value,
    )
    trace_res = await db_session.execute(trace_stmt)
    event = trace_res.scalar_one()
    assert event.target_type == "payment"
    assert event.actor_user_id == user_mgr.id

    # 3. Correcting an already corrected payment raises ValidationException
    with pytest.raises(ValidationException, match="already been corrected"):
        await service.correct_payment(
            original.id,
            PaymentCorrectionRequest(amount_minor=50000, reason="Second correction"),
            user_owner.id,
            MemberRole.OWNER,
        )

    # 4. Voiding a corrected payment raises ValidationException
    with pytest.raises(ValidationException, match="Cannot void a payment that has already been corrected"):
        await service.void_payment(
            original.id,
            PaymentVoidRequest(reason="Try voiding corrected"),
            user_owner.id,
            MemberRole.OWNER,
        )

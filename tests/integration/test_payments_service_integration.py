"""Integration tests for Payment Recording Service (PAY-002)."""

import uuid
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.orders.models import Order
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.payments.enums import PaymentChannel, PaymentStatus
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import PaymentService
from app.modules.auth.models import User


async def _create_test_org(db_session: AsyncSession, name: str = "Payment Service Org") -> Organization:
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


async def _create_test_user(db_session: AsyncSession, prefix: str = "serv_payer") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Service Payer",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_test_customer(db_session: AsyncSession, org_id: uuid.UUID) -> Customer:
    customer = Customer(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Service Customer",
        phone="03001112233",
        status=CustomerStatus.ACTIVE.value,
    )
    db_session.add(customer)
    await db_session.flush()
    return customer


async def _create_test_order(
    db_session: AsyncSession, org_id: uuid.UUID, order_number: str = "ORD-SERV-1", status: str = "active"
) -> Order:
    order = Order(
        id=uuid.uuid4(),
        organization_id=org_id,
        order_number=order_number,
        order_total_minor=60000,
        currency_code="PKR",
        status=status,
    )
    db_session.add(order)
    await db_session.flush()
    return order


@pytest.mark.asyncio
async def test_record_payment_happy_path_and_roles(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Roles Org")
    user = await _create_test_user(db_session, "worker")
    customer = await _create_test_customer(db_session, org.id)
    order = await _create_test_order(db_session, org.id, "ORD-ROLES-1")

    service = PaymentService(db_session, org.id)

    # 1. Staff can record payment (Permission.PAYMENTS_CREATE)
    payload_staff = PaymentCreate(
        amount_minor=10000,
        channel=PaymentChannel.CASH,
        customer_id=customer.id,
        order_id=order.id,
        account_label="Cash Drawer",
        external_reference="RCPT-STAFF-1",
        notes="Cash at counter",
    )
    p_staff = await service.record_payment(payload_staff, user.id, MemberRole.STAFF)
    assert p_staff.id is not None
    assert p_staff.amount_minor == 10000
    assert p_staff.channel == "cash"
    assert p_staff.status == "active"

    # 2. Manager can record payment
    payload_mgr = PaymentCreate(
        amount_minor=20000,
        channel=PaymentChannel.BANK_TRANSFER,
        account_label="Bank A",
        external_reference="TXN-MGR-1",
    )
    p_mgr = await service.record_payment(payload_mgr, user.id, MemberRole.MANAGER)
    assert p_mgr.id is not None
    assert p_mgr.amount_minor == 20000

    # 3. Owner can record payment
    payload_owner = PaymentCreate(
        amount_minor=30000,
        channel=PaymentChannel.DIGITAL,
        account_label="Easypaisa",
        external_reference="DIG-OWNER-1",
    )
    p_owner = await service.record_payment(payload_owner, user.id, MemberRole.OWNER)
    assert p_owner.id is not None
    assert p_owner.amount_minor == 30000


@pytest.mark.asyncio
async def test_record_payment_deterministic_validations(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Validations Org")
    user = await _create_test_user(db_session, "validator")
    service = PaymentService(db_session, org.id)

    # Negative amount at Pydantic layer
    with pytest.raises(Exception):
        PaymentCreate(amount_minor=-500, channel=PaymentChannel.CASH)

    # Negative amount at Service layer
    with pytest.raises(ValidationException, match="must be greater than zero"):
        await service.record_payment(
            PaymentCreate.model_construct(amount_minor=-500, channel=PaymentChannel.CASH, currency_code="PKR"),
            user.id,
            MemberRole.STAFF,
        )

    # Zero amount at Service layer
    with pytest.raises(ValidationException, match="must be greater than zero"):
        await service.record_payment(
            PaymentCreate.model_construct(amount_minor=0, channel=PaymentChannel.CASH, currency_code="PKR"),
            user.id,
            MemberRole.STAFF,
        )


@pytest.mark.asyncio
async def test_duplicate_external_reference_blocked_in_same_org(db_session: AsyncSession) -> None:
    org1 = await _create_test_org(db_session, "Dup Org 1")
    org2 = await _create_test_org(db_session, "Dup Org 2")
    user = await _create_test_user(db_session, "duptester")

    service1 = PaymentService(db_session, org1.id)
    service2 = PaymentService(db_session, org2.id)

    ref = "REF-UNIQUE-101"

    # First recording in Org 1 succeeds
    p1 = await service1.record_payment(
        PaymentCreate(amount_minor=5000, channel=PaymentChannel.BANK_TRANSFER, external_reference=ref),
        user.id,
        MemberRole.STAFF,
    )
    assert p1.id is not None

    # Duplicate recording in same Org 1 is BLOCKED with 422 ValidationException
    with pytest.raises(ValidationException, match="already exists in this organization"):
        await service1.record_payment(
            PaymentCreate(amount_minor=6000, channel=PaymentChannel.BANK_TRANSFER, external_reference=ref),
            user.id,
            MemberRole.STAFF,
        )

    # Same reference in different Org 2 is ALLOWED
    p2 = await service2.record_payment(
        PaymentCreate(amount_minor=7000, channel=PaymentChannel.BANK_TRANSFER, external_reference=ref),
        user.id,
        MemberRole.STAFF,
    )
    assert p2.id is not None


@pytest.mark.asyncio
async def test_optional_order_and_customer_tenant_safety(db_session: AsyncSession) -> None:
    org_a = await _create_test_org(db_session, "Tenant Safe Org A")
    org_b = await _create_test_org(db_session, "Tenant Safe Org B")
    user = await _create_test_user(db_session, "tenantuser")

    cust_b = await _create_test_customer(db_session, org_b.id)
    order_b = await _create_test_order(db_session, org_b.id, "ORD-B-1")
    voided_order_a = await _create_test_order(db_session, org_a.id, "ORD-VOID-A", status="voided")

    service_a = PaymentService(db_session, org_a.id)

    # Cross-tenant customer rejected
    with pytest.raises(ValidationException, match="Referenced customer does not exist in this organization"):
        await service_a.record_payment(
            PaymentCreate(amount_minor=5000, channel=PaymentChannel.CASH, customer_id=cust_b.id),
            user.id,
            MemberRole.STAFF,
        )

    # Cross-tenant order rejected
    with pytest.raises(ValidationException, match="Referenced order does not exist in this organization"):
        await service_a.record_payment(
            PaymentCreate(amount_minor=5000, channel=PaymentChannel.CASH, order_id=order_b.id),
            user.id,
            MemberRole.STAFF,
        )

    # Voided order rejected
    with pytest.raises(ValidationException, match="Cannot record payment against a voided order"):
        await service_a.record_payment(
            PaymentCreate(amount_minor=5000, channel=PaymentChannel.CASH, order_id=voided_order_a.id),
            user.id,
            MemberRole.STAFF,
        )


@pytest.mark.asyncio
async def test_get_payment_and_tenant_isolation(db_session: AsyncSession) -> None:
    org_a = await _create_test_org(db_session, "Isolation Org A")
    org_b = await _create_test_org(db_session, "Isolation Org B")
    user = await _create_test_user(db_session, "reader")

    service_a = PaymentService(db_session, org_a.id)
    service_b = PaymentService(db_session, org_b.id)

    p_a = await service_a.record_payment(
        PaymentCreate(amount_minor=12000, channel=PaymentChannel.CASH),
        user.id,
        MemberRole.OWNER,
    )

    # Org A can read
    loaded = await service_a.get_payment(p_a.id, MemberRole.STAFF)
    assert loaded.id == p_a.id

    # Org B trying to read Org A's payment gets 404 (IDOR non-disclosure)
    with pytest.raises(NotFoundException, match="Payment not found"):
        await service_b.get_payment(p_a.id, MemberRole.OWNER)


@pytest.mark.asyncio
async def test_daily_payment_totals_calculation(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Daily Totals Org")
    user = await _create_test_user(db_session, "totaller")
    service = PaymentService(db_session, org.id)

    today = date(2026, 9, 25)
    rec_today = datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc)
    rec_yesterday = datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc)

    # Add 2 payments today
    await service.record_payment(
        PaymentCreate(amount_minor=15000, channel=PaymentChannel.CASH, received_at=rec_today),
        user.id,
        MemberRole.STAFF,
    )
    await service.record_payment(
        PaymentCreate(amount_minor=25000, channel=PaymentChannel.BANK_TRANSFER, received_at=rec_today),
        user.id,
        MemberRole.STAFF,
    )

    # Add 1 payment yesterday
    await service.record_payment(
        PaymentCreate(amount_minor=50000, channel=PaymentChannel.CASH, received_at=rec_yesterday),
        user.id,
        MemberRole.STAFF,
    )

    # Day total for today must be 15000 + 25000 = 40000
    today_total = await service.get_daily_payment_total(today, MemberRole.STAFF)
    assert today_total == 40000

    # Day total for yesterday must be 50000
    yesterday_total = await service.get_daily_payment_total(date(2026, 9, 24), MemberRole.STAFF)
    assert yesterday_total == 50000

"""PostgreSQL integration tests for Payment persistence and constraints (PAY-001)."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationException
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.orders.models import Order
from app.modules.organizations.models import Organization
from app.modules.payments.enums import PaymentChannel, PaymentStatus
from app.modules.payments.models import Payment
from app.modules.payments.repository import PaymentRepository
from app.modules.auth.models import User


async def _create_test_org(db_session: AsyncSession, name: str = "Payment Org") -> Organization:
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


async def _create_test_user(db_session: AsyncSession, email_prefix: str = "payer") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Payer User",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_test_customer(db_session: AsyncSession, org_id: uuid.UUID, phone: str = "03001234567") -> Customer:
    customer = Customer(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Test Customer",
        phone=phone,
        status=CustomerStatus.ACTIVE.value,
    )
    db_session.add(customer)
    await db_session.flush()
    return customer


async def _create_test_order(db_session: AsyncSession, org_id: uuid.UUID, order_number: str = "ORD-0001") -> Order:
    order = Order(
        id=uuid.uuid4(),
        organization_id=org_id,
        order_number=order_number,
        order_total_minor=50000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(order)
    await db_session.flush()
    return order


@pytest.mark.asyncio
async def test_valid_payment_persistence(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Valid Payment Org")
    user = await _create_test_user(db_session, "creator")
    customer = await _create_test_customer(db_session, org.id)
    order = await _create_test_order(db_session, org.id, "ORD-PAY-01")

    payment_id = uuid.uuid4()
    payment = Payment(
        id=payment_id,
        organization_id=org.id,
        customer_id=customer.id,
        order_id=order.id,
        amount_minor=25000,
        currency_code="PKR",
        received_at=datetime.now(timezone.utc),
        channel=PaymentChannel.CASH.value,
        account_label="Cash Counter 1",
        external_reference="RCPT-00123",
        notes="Received partial cash payment",
        status=PaymentStatus.ACTIVE.value,
        created_by_user_id=user.id,
    )
    db_session.add(payment)
    await db_session.flush()

    # Query back
    stmt = select(Payment).where(Payment.id == payment_id)
    res = await db_session.execute(stmt)
    saved = res.scalar_one()

    assert saved.id == payment_id
    assert saved.organization_id == org.id
    assert saved.customer_id == customer.id
    assert saved.order_id == order.id
    assert saved.amount_minor == 25000
    assert saved.currency_code == "PKR"
    assert saved.channel == "cash"
    assert saved.account_label == "Cash Counter 1"
    assert saved.external_reference == "RCPT-00123"
    assert saved.status == "active"
    assert saved.created_by_user_id == user.id


@pytest.mark.asyncio
async def test_payment_monetary_check_constraint(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Monetary Check Org")

    # Zero amount must fail
    zero_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=0,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(zero_pay)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Negative amount must fail
    neg_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=-500,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(neg_pay)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_payment_status_and_channel_constraints(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Enum Check Org")

    # Invalid channel must fail
    bad_channel = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=1000,
        channel="crypto",
        status="active",
    )
    db_session.add(bad_channel)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Invalid status must fail
    bad_status = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=1000,
        channel=PaymentChannel.CASH.value,
        status="settled",  # Not in active, voided, corrected
    )
    db_session.add(bad_status)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Invalid currency code length must fail
    bad_curr = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=1000,
        channel=PaymentChannel.CASH.value,
        currency_code="PK",  # 2 characters instead of 3
        status="active",
    )
    db_session.add(bad_curr)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_foreign_key_behavior(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "FK Check Org")

    # Non-existent customer FK fails
    non_existent_cust_id = uuid.uuid4()
    bad_cust_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        customer_id=non_existent_cust_id,
        amount_minor=1000,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(bad_cust_pay)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # Non-existent order FK fails
    non_existent_order_id = uuid.uuid4()
    bad_order_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        order_id=non_existent_order_id,
        amount_minor=1000,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(bad_order_pay)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_cross_organization_relationship_rejection(db_session: AsyncSession) -> None:
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    cust_b = await _create_test_customer(db_session, org_b.id, "03009999999")
    order_b = await _create_test_order(db_session, org_b.id, "ORD-B-01")

    # 1. DB trigger rejects cross-org order
    cross_order_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        order_id=order_b.id,
        amount_minor=5000,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(cross_order_pay)
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()
    assert "Cross-organization reference" in str(exc_info.value)
    await db_session.rollback()

    # 2. DB trigger rejects cross-org customer
    cross_cust_pay = Payment(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        customer_id=cust_b.id,
        amount_minor=5000,
        channel=PaymentChannel.CASH.value,
        status="active",
    )
    db_session.add(cross_cust_pay)
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()
    assert "Cross-organization reference" in str(exc_info.value)
    await db_session.rollback()

    # 3. Repository also cleanly rejects cross-org order with ValidationException
    repo_a = PaymentRepository(db_session, org_a.id)
    with pytest.raises(ValidationException, match="Referenced order does not exist in this organization"):
        await repo_a.create_payment(
            amount_minor=5000,
            channel="cash",
            order_id=order_b.id,
        )

    # 4. Repository cleanly rejects cross-org customer with ValidationException
    with pytest.raises(ValidationException, match="Referenced customer does not exist in this organization"):
        await repo_a.create_payment(
            amount_minor=5000,
            channel="cash",
            customer_id=cust_b.id,
        )


@pytest.mark.asyncio
async def test_payment_repository_operations(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Repo Org")
    customer = await _create_test_customer(db_session, org.id, "03008888888")
    order = await _create_test_order(db_session, org.id, "ORD-REPO-1")

    repo = PaymentRepository(db_session, org.id)

    # Create payment via repo
    payment = await repo.create_payment(
        amount_minor=15000,
        channel="bank_transfer",
        customer_id=customer.id,
        order_id=order.id,
        account_label="Meezan Bank",
        external_reference="TXN-987654",
        notes="Online payment receipt",
    )
    assert payment.id is not None
    assert payment.amount_minor == 15000
    assert payment.channel == "bank_transfer"

    # Fetch by external reference
    found = await repo.get_by_external_reference("TXN-987654")
    assert found is not None
    assert found.id == payment.id

    # List payments with filters
    items, total = await repo.list_payments(customer_id=customer.id)
    assert total == 1
    assert items[0].id == payment.id

    items_by_channel, count_ch = await repo.list_payments(channel="cash")
    assert count_ch == 0

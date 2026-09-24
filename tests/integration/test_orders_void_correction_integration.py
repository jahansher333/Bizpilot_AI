"""PostgreSQL integration tests for order void and correction operations (ORD-005)."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthorizationException, ConflictException, NotFoundException, ValidationException
from app.modules.auth.models import User
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import (
    OrderCorrectRequestSchema,
    OrderCreateSchema,
    OrderItemCreateSchema,
    OrderVoidRequestSchema,
)
from app.modules.orders.service import OrderService
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.trace.enums import TraceAction
from app.modules.trace.models import InternalTraceEvent


async def _create_org(db_session: AsyncSession, name: str) -> Organization:
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


async def _create_user(db_session: AsyncSession, prefix: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{prefix.lower()}_{uuid.uuid4().hex[:6]}@example.com",
        display_name=f"{prefix} User",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_product(
    db_session: AsyncSession,
    org_id: uuid.UUID,
    code: str,
    price: int = 50000,
    status: str = ProductStatus.ACTIVE.value,
) -> Product:
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code=code,
        name=f"Product {code}",
        base_unit="piece",
        default_price_minor=price,
        currency_code="PKR",
        status=status,
    )
    db_session.add(prod)
    await db_session.flush()
    return prod


async def _create_balance(
    db_session: AsyncSession,
    org_id: uuid.UUID,
    prod_id: uuid.UUID,
    qty: int = 20,
) -> InventoryBalance:
    bal = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=prod_id,
        on_hand_quantity=qty,
        version=1,
    )
    db_session.add(bal)
    await db_session.flush()
    return bal


async def _create_customer(
    db_session: AsyncSession,
    org_id: uuid.UUID,
    phone: str = "03001234567",
    status: str = CustomerStatus.ACTIVE.value,
) -> Customer:
    cust = Customer(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Test Customer",
        phone=phone,
        status=status,
    )
    db_session.add(cust)
    await db_session.flush()
    return cust


@pytest.mark.asyncio
async def test_owner_void_order_success(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Void Org 1")
    owner = await _create_user(db_session, "owner1")
    prod1 = await _create_product(db_session, org.id, "V-PROD-1", price=10000)
    prod2 = await _create_product(db_session, org.id, "V-PROD-2", price=25000)
    bal1 = await _create_balance(db_session, org.id, prod1.id, qty=30)
    bal2 = await _create_balance(db_session, org.id, prod2.id, qty=40)
    customer = await _create_customer(db_session, org.id, "03001111111")

    service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=owner.id,
        actor_role=MemberRole.OWNER.value,
    )

    create_req = OrderCreateSchema(
        customer_id=customer.id,
        items=[
            OrderItemCreateSchema(product_id=prod1.id, quantity=5, unit_price_minor=10000),
            OrderItemCreateSchema(product_id=prod2.id, quantity=3, unit_price_minor=25000),
        ],
    )
    order = await service.create_order(create_req)
    assert order.status == OrderStatus.ACTIVE.value

    # Balances deducted: 30 - 5 = 25, 40 - 3 = 37
    await db_session.refresh(bal1)
    await db_session.refresh(bal2)
    assert bal1.on_hand_quantity == 25
    assert bal2.on_hand_quantity == 37

    # Owner voids the order
    void_req = OrderVoidRequestSchema(reason="Customer requested cancellation")
    voided = await service.void_order(order.id, void_req, idempotency_key="idemp-void-1")
    assert voided.status == OrderStatus.VOIDED.value
    assert voided.voided_at is not None

    # Balances restored: 25 + 5 = 30, 37 + 3 = 40
    await db_session.refresh(bal1)
    await db_session.refresh(bal2)
    assert bal1.on_hand_quantity == 30
    assert bal2.on_hand_quantity == 40

    # Inventory movements should include VOID_REVERSAL
    stmt = (
        select(InventoryMovement)
        .where(
            InventoryMovement.organization_id == org.id,
            InventoryMovement.movement_type == MovementType.VOID_REVERSAL.value,
            InventoryMovement.source_type == MovementSourceType.ORDER.value,
            InventoryMovement.source_id == order.id,
        )
        .order_by(InventoryMovement.product_id)
    )
    movements = (await db_session.execute(stmt)).scalars().all()
    assert len(movements) == 2
    assert {m.product_id: m.quantity_delta for m in movements} == {prod1.id: 5, prod2.id: 3}

    # Trace event recorded
    trace_stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.organization_id == org.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_VOIDED.value,
        InternalTraceEvent.target_id == order.id,
    )
    trace = (await db_session.execute(trace_stmt)).scalar_one_or_none()
    assert trace is not None
    assert trace.event_metadata["reason"] == "Customer requested cancellation"

    # Idempotent replay
    replayed = await service.void_order(order.id, void_req, idempotency_key="idemp-void-1")
    assert replayed.id == order.id
    assert replayed.status == OrderStatus.VOIDED.value


@pytest.mark.asyncio
async def test_non_owner_void_order_denied(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Void Org 2")
    owner = await _create_user(db_session, "owner2")
    manager = await _create_user(db_session, "mgr2")
    staff = await _create_user(db_session, "stf2")
    prod = await _create_product(db_session, org.id, "V-PROD-3", price=10000)
    await _create_balance(db_session, org.id, prod.id, qty=30)
    customer = await _create_customer(db_session, org.id, "03002222222")

    owner_service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=owner.id,
        actor_role=MemberRole.OWNER.value,
    )
    order = await owner_service.create_order(
        OrderCreateSchema(
            customer_id=customer.id,
            items=[OrderItemCreateSchema(product_id=prod.id, quantity=2, unit_price_minor=10000)],
        )
    )

    manager_service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=manager.id,
        actor_role=MemberRole.MANAGER.value,
    )
    with pytest.raises(AuthorizationException) as exc_info:
        await manager_service.void_order(order.id, OrderVoidRequestSchema(reason="Manager trying"))
    assert "Permission denied" in str(exc_info.value)

    staff_service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=staff.id,
        actor_role=MemberRole.STAFF.value,
    )
    with pytest.raises(AuthorizationException) as exc_info_staff:
        await staff_service.void_order(order.id, OrderVoidRequestSchema(reason="Staff trying"))
    assert "Permission denied" in str(exc_info_staff.value)


@pytest.mark.asyncio
async def test_manager_correct_order_success(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Correct Org 1")
    manager = await _create_user(db_session, "mgr3")
    prod1 = await _create_product(db_session, org.id, "C-PROD-1", price=10000)
    prod2 = await _create_product(db_session, org.id, "C-PROD-2", price=20000)
    bal1 = await _create_balance(db_session, org.id, prod1.id, qty=10)
    bal2 = await _create_balance(db_session, org.id, prod2.id, qty=10)
    customer = await _create_customer(db_session, org.id, "03003333333")

    service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=manager.id,
        actor_role=MemberRole.MANAGER.value,
    )

    # Initial order: 4x prod1 (minor total: 40000)
    original_order = await service.create_order(
        OrderCreateSchema(
            customer_id=customer.id,
            items=[OrderItemCreateSchema(product_id=prod1.id, quantity=4, unit_price_minor=10000)],
        )
    )
    await db_session.refresh(bal1)
    assert bal1.on_hand_quantity == 6

    # Manager corrects order: change to 2x prod1 and 3x prod2
    correct_req = OrderCorrectRequestSchema(
        reason="Customer changed order items",
        items=[
            OrderItemCreateSchema(product_id=prod1.id, quantity=2, unit_price_minor=10000),
            OrderItemCreateSchema(product_id=prod2.id, quantity=3, unit_price_minor=20000),
        ],
    )
    replacement = await service.correct_order(original_order.id, correct_req, idempotency_key="idemp-corr-1")
    assert replacement.status == OrderStatus.ACTIVE.value
    assert replacement.corrects_order_id == original_order.id
    assert replacement.order_total_minor == 80000  # (2 * 10000) + (3 * 20000)

    # Verify original order updated
    db_orig = await service.get_order(original_order.id)
    assert db_orig.status == OrderStatus.CORRECTED.value
    assert db_orig.replaced_by_order_id == replacement.id

    # Balances: prod1 was 6, +4 restored = 10, -2 deducted = 8.
    # prod2 was 10, -3 deducted = 7.
    await db_session.refresh(bal1)
    await db_session.refresh(bal2)
    assert bal1.on_hand_quantity == 8
    assert bal2.on_hand_quantity == 7

    # Trace event recorded for correction
    trace_stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.organization_id == org.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_CORRECTED.value,
        InternalTraceEvent.target_id == original_order.id,
    )
    trace = (await db_session.execute(trace_stmt)).scalar_one_or_none()
    assert trace is not None
    assert trace.event_metadata["original_order_number"] == original_order.order_number
    assert trace.event_metadata["replacement_order_number"] == replacement.order_number

    # Idempotent replay
    replayed = await service.correct_order(original_order.id, correct_req, idempotency_key="idemp-corr-1")
    assert replayed.id == replacement.id


@pytest.mark.asyncio
async def test_staff_correct_order_denied(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Correct Org 2")
    owner = await _create_user(db_session, "owner4")
    staff = await _create_user(db_session, "staff4")
    prod = await _create_product(db_session, org.id, "C-PROD-3", price=10000)
    await _create_balance(db_session, org.id, prod.id, qty=30)
    customer = await _create_customer(db_session, org.id, "03004444444")

    owner_service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=owner.id,
        actor_role=MemberRole.OWNER.value,
    )
    order = await owner_service.create_order(
        OrderCreateSchema(
            customer_id=customer.id,
            items=[OrderItemCreateSchema(product_id=prod.id, quantity=2, unit_price_minor=10000)],
        )
    )

    staff_service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=staff.id,
        actor_role=MemberRole.STAFF.value,
    )
    with pytest.raises(AuthorizationException) as exc_info:
        await staff_service.correct_order(
            order.id,
            OrderCorrectRequestSchema(
                reason="Staff trying correction",
                items=[OrderItemCreateSchema(product_id=prod.id, quantity=1, unit_price_minor=10000)],
            ),
        )
    assert "Permission denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_correction_insufficient_stock_aborts_cleanly(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Correct Stock Org")
    owner = await _create_user(db_session, "owner5")
    prod1 = await _create_product(db_session, org.id, "CS-PROD-1", price=10000)
    prod2 = await _create_product(db_session, org.id, "CS-PROD-2", price=20000)
    bal1 = await _create_balance(db_session, org.id, prod1.id, qty=5)
    bal2 = await _create_balance(db_session, org.id, prod2.id, qty=2)
    customer = await _create_customer(db_session, org.id, "03005555555")

    service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=owner.id,
        actor_role=MemberRole.OWNER.value,
    )

    # Initial order takes 3 prod1 (remaining: 2)
    order = await service.create_order(
        OrderCreateSchema(
            customer_id=customer.id,
            items=[OrderItemCreateSchema(product_id=prod1.id, quantity=3, unit_price_minor=10000)],
        )
    )
    await db_session.refresh(bal1)
    await db_session.refresh(bal2)
    assert bal1.on_hand_quantity == 2
    assert bal2.on_hand_quantity == 2

    # Attempt correction requiring 10 prod2 (only 2 in stock)
    correct_req = OrderCorrectRequestSchema(
        reason="Oversold product 2",
        items=[
            OrderItemCreateSchema(product_id=prod2.id, quantity=10, unit_price_minor=20000),
        ],
    )
    with pytest.raises(ValidationException) as exc_info:
        await service.correct_order(order.id, correct_req)
    assert "Insufficient stock" in str(exc_info.value)

    # Original order MUST still be active
    original = await service.get_order(order.id)
    assert original.status == OrderStatus.ACTIVE.value
    assert original.replaced_by_order_id is None

    # Balances unchanged
    await db_session.refresh(bal1)
    await db_session.refresh(bal2)
    assert bal1.on_hand_quantity == 2
    assert bal2.on_hand_quantity == 2


@pytest.mark.asyncio
async def test_cannot_void_or_correct_non_active_order(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Status Check Org")
    owner = await _create_user(db_session, "owner6")
    prod = await _create_product(db_session, org.id, "SC-PROD-1", price=10000)
    await _create_balance(db_session, org.id, prod.id, qty=20)
    customer = await _create_customer(db_session, org.id, "03006666666")

    service = OrderService(
        session=db_session,
        organization_id=org.id,
        actor_user_id=owner.id,
        actor_role=MemberRole.OWNER.value,
    )

    order = await service.create_order(
        OrderCreateSchema(
            customer_id=customer.id,
            items=[OrderItemCreateSchema(product_id=prod.id, quantity=2, unit_price_minor=10000)],
        )
    )

    # Void order once
    await service.void_order(order.id, OrderVoidRequestSchema(reason="Void 1"))

    # Try voiding again without idempotency key
    with pytest.raises(ConflictException) as exc_info:
        await service.void_order(order.id, OrderVoidRequestSchema(reason="Void again"))
    assert "already voided" in str(exc_info.value)

    # Try correcting voided order
    with pytest.raises(ConflictException) as exc_info_corr:
        await service.correct_order(
            order.id,
            OrderCorrectRequestSchema(
                reason="Correct voided",
                items=[OrderItemCreateSchema(product_id=prod.id, quantity=1, unit_price_minor=10000)],
            ),
        )
    assert "Cannot correct a voided order" in str(exc_info_corr.value)

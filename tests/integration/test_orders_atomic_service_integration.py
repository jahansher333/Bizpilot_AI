"""PostgreSQL integration tests for atomic order and inventory operations (ORD-003)."""

from __future__ import annotations

import asyncio
import uuid
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import OrderCreateSchema, OrderItemCreateSchema
from app.modules.orders.service import OrderService
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product


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
async def test_atomic_order_creation_success(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Atomic Order Org 1")
    prod = await _create_product(db_session, org.id, "SKU-A1", price=15000)
    await _create_balance(db_session, org.id, prod.id, qty=25)
    cust = await _create_customer(db_session, org.id, phone="03001111111")
    org_id = org.id
    prod_id = prod.id
    cust_id = cust.id
    prod_name = prod.name
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_role=MemberRole.STAFF,
    )

    req = OrderCreateSchema(
        customer_id=cust_id,
        items=[
            OrderItemCreateSchema(
                product_id=prod_id,
                quantity=4,
                unit_price_minor=15000,
            )
        ],
    )

    result = await service.create_order(req)

    assert result.order_number == "ORD-0001"
    assert result.order_total_minor == 60000
    assert result.status == OrderStatus.ACTIVE.value
    assert len(result.items) == 1
    assert result.items[0].product_name_snapshot == prod_name
    assert result.items[0].line_total_minor == 60000

    # Verify database state
    bal_res = await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_id)
    )
    db_bal = bal_res.scalar_one()
    assert db_bal.on_hand_quantity == 21
    assert db_bal.version == 2

    # Verify inventory movement
    mov_res = await db_session.execute(
        select(InventoryMovement).where(
            InventoryMovement.product_id == prod_id,
            InventoryMovement.source_type == MovementSourceType.ORDER.value,
        )
    )
    movement = mov_res.scalar_one()
    assert movement.movement_type == MovementType.SALE.value
    assert movement.quantity_delta == -4
    assert movement.source_id == result.id


@pytest.mark.asyncio
async def test_insufficient_stock_rollback_leaves_state_intact(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Atomic Order Org 2")
    prod = await _create_product(db_session, org.id, "SKU-A2", price=20000)
    await _create_balance(db_session, org.id, prod.id, qty=5)
    org_id = org.id
    prod_id = prod.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_role=MemberRole.OWNER,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=prod_id,
                quantity=10,  # exceeds 5
                unit_price_minor=20000,
            )
        ],
    )

    with pytest.raises(ValidationException) as exc_info:
        await service.create_order(req)

    assert "Insufficient stock" in str(exc_info.value)

    # Verify balance was NOT decremented
    bal_res = await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_id)
    )
    db_bal = bal_res.scalar_one()
    assert db_bal.on_hand_quantity == 5

    # Verify no order or movement was committed
    orders_res = await db_session.execute(
        select(Order).where(Order.organization_id == org_id)
    )
    assert len(orders_res.scalars().all()) == 0

    mov_res = await db_session.execute(
        select(InventoryMovement).where(InventoryMovement.organization_id == org_id)
    )
    assert len(mov_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_multi_item_order_all_or_nothing(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Atomic Order Org 3")
    prod_a = await _create_product(db_session, org.id, "SKU-M1", price=1000)
    prod_b = await _create_product(db_session, org.id, "SKU-M2", price=2000)
    await _create_balance(db_session, org.id, prod_a.id, qty=10)
    await _create_balance(db_session, org.id, prod_b.id, qty=2)
    org_id = org.id
    prod_a_id = prod_a.id
    prod_b_id = prod_b.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_role=MemberRole.MANAGER,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(product_id=prod_a_id, quantity=5, unit_price_minor=1000),
            OrderItemCreateSchema(product_id=prod_b_id, quantity=5, unit_price_minor=2000),  # exceeds 2
        ],
    )

    with pytest.raises(ValidationException):
        await service.create_order(req)

    # Product A must remain completely unaffected (rollback)
    bal_a = (await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_a_id)
    )).scalar_one()
    assert bal_a.on_hand_quantity == 10

    bal_b = (await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_b_id)
    )).scalar_one()
    assert bal_b.on_hand_quantity == 2


@pytest.mark.asyncio
async def test_archived_product_order_fails_and_rolls_back(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Atomic Order Org 4")
    archived_prod = await _create_product(
        db_session, org.id, "SKU-ARCH", price=5000, status=ProductStatus.ARCHIVED.value
    )
    await _create_balance(db_session, org.id, archived_prod.id, qty=50)
    org_id = org.id
    archived_prod_id = archived_prod.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_role=MemberRole.STAFF,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=archived_prod_id,
                quantity=1,
                unit_price_minor=5000,
            )
        ],
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_order(req)

    assert "Cannot order archived product" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tenant_isolation_foreign_product_invisible(db_session: AsyncSession) -> None:
    org_a = await _create_org(db_session, "Atomic Org A")
    org_b = await _create_org(db_session, "Atomic Org B")
    prod_b = await _create_product(db_session, org_b.id, "SKU-B1", price=3000)
    await _create_balance(db_session, org_b.id, prod_b.id, qty=10)
    org_a_id = org_a.id
    prod_b_id = prod_b.id
    await db_session.commit()

    # Org A tries to order Org B's product
    service_a = OrderService(
        session=db_session,
        organization_id=org_a_id,
        actor_role=MemberRole.STAFF,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=prod_b_id,
                quantity=1,
                unit_price_minor=3000,
            )
        ],
    )

    with pytest.raises(NotFoundException):
        await service_a.create_order(req)

    # Org B stock remains untouched
    bal_b = (await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_b_id)
    )).scalar_one()
    assert bal_b.on_hand_quantity == 10


@pytest.mark.asyncio
async def test_concurrent_order_creation_serialization(db_engine: AsyncEngine) -> None:
    """Verify concurrent orders serialize under pessimistic row locking without overselling."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            display_name="Concurrency Order Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status="active",
        )
        session.add(org)
        await session.flush()

        prod = Product(
            id=prod_id,
            organization_id=org_id,
            code="CONCUR-ORD-SKU",
            name="Concurrent Order Product",
            base_unit="piece",
            default_price_minor=1000,
            currency_code="PKR",
            status="active",
        )
        session.add(prod)
        await session.flush()

        bal = InventoryBalance(
            id=uuid.uuid4(),
            organization_id=org_id,
            product_id=prod_id,
            on_hand_quantity=10,  # 10 units available
            version=1,
        )
        session.add(bal)
        await session.commit()

    try:
        # 5 concurrent workers each attempting to purchase 3 units (total 15 units demanded, 10 available)
        successful_orders = []
        failed_orders = []

        async def worker(worker_id: int) -> None:
            async with session_factory() as session:
                service = OrderService(
                    session=session,
                    organization_id=org_id,
                    actor_role=MemberRole.STAFF,
                )
                req = OrderCreateSchema(
                    items=[
                        OrderItemCreateSchema(
                            product_id=prod_id,
                            quantity=3,
                            unit_price_minor=1000,
                        )
                    ],
                )
                try:
                    order = await service.create_order(req)
                    await session.commit()
                    successful_orders.append(order)
                except ValidationException as exc:
                    await session.rollback()
                    failed_orders.append(exc)

        workers = [worker(i) for i in range(5)]
        await asyncio.gather(*workers)

        # Exactly 3 orders succeed (3 * 3 = 9 units), remaining 2 fail due to insufficient stock (1 unit left)
        assert len(successful_orders) == 3
        assert len(failed_orders) == 2

        # Verify final balance is exactly 1 unit
        async with session_factory() as session:
            final_bal = (await session.execute(
                select(InventoryBalance).where(InventoryBalance.product_id == prod_id)
            )).scalar_one()
            assert final_bal.on_hand_quantity == 1

            # Exactly 3 orders in database
            orders = (await session.execute(
                select(Order).where(Order.organization_id == org_id)
            )).scalars().all()
            assert len(orders) == 3

            # Exactly 3 sale movements in database
            movements = (await session.execute(
                select(InventoryMovement).where(
                    InventoryMovement.organization_id == org_id,
                    InventoryMovement.product_id == prod_id,
                )
            )).scalars().all()
            assert len(movements) == 3
            assert all(m.movement_type == MovementType.SALE.value for m in movements)
            assert all(m.quantity_delta == -3 for m in movements)

    finally:
        # Clean up
        async with session_factory() as session:
            await session.execute(delete(OrderItem).where(OrderItem.organization_id == org_id))
            await session.execute(delete(Order).where(Order.organization_id == org_id))
            await session.execute(delete(InventoryMovement).where(InventoryMovement.organization_id == org_id))
            await session.execute(delete(InventoryBalance).where(InventoryBalance.organization_id == org_id))
            await session.execute(delete(Product).where(Product.organization_id == org_id))
            await session.execute(delete(Organization).where(Organization.id == org_id))
            await session.commit()


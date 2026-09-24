"""PostgreSQL integration tests for Order and OrderItem persistence (ORD-001)."""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.repository import OrderRepository
from app.modules.organizations.models import Organization
from app.modules.products.models import Product


async def _create_test_org(db_session: AsyncSession, name: str = "Order Org") -> Organization:
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


async def _create_test_product(db_session: AsyncSession, org_id: uuid.UUID, code: str) -> Product:
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code=code,
        name=f"Product {code}",
        base_unit="piece",
        default_price_minor=25000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()
    return prod


@pytest.mark.asyncio
async def test_order_persistence_and_check_constraints(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Order Constraints Org")
    prod = await _create_test_product(db_session, org.id, "PROD-10")

    order_id = uuid.uuid4()
    order = Order(
        id=order_id,
        organization_id=org.id,
        order_number="ORD-0001",
        customer_id=None,
        status=OrderStatus.ACTIVE.value,
        order_total_minor=50000,
        currency_code="PKR",
    )
    db_session.add(order)
    await db_session.flush()

    # Valid OrderItem
    item = OrderItem(
        id=uuid.uuid4(),
        organization_id=org.id,
        order_id=order_id,
        product_id=prod.id,
        product_name_snapshot=prod.name,
        product_code_snapshot=prod.code,
        unit_snapshot=prod.base_unit,
        quantity=2,
        unit_price_minor=25000,
        line_total_minor=50000,  # 2 * 25000 == 50000
        currency_code="PKR",
    )
    db_session.add(item)
    await db_session.flush()
    assert item.id is not None

    # Line total calculation constraint: line_total != quantity * unit_price MUST FAIL
    bad_calc_item = OrderItem(
        id=uuid.uuid4(),
        organization_id=org.id,
        order_id=order_id,
        product_id=prod.id,
        product_name_snapshot=prod.name,
        product_code_snapshot=prod.code,
        unit_snapshot=prod.base_unit,
        quantity=2,
        unit_price_minor=25000,
        line_total_minor=99999,  # Inconsistent with 2 * 25000
        currency_code="PKR",
    )
    db_session.add(bad_calc_item)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_order_number_unique_per_organization(db_session: AsyncSession) -> None:
    org1 = await _create_test_org(db_session, "Org 1 Order Number")
    org2 = await _create_test_org(db_session, "Org 2 Order Number")

    # Order 1 in Org 1
    o1 = Order(
        id=uuid.uuid4(),
        organization_id=org1.id,
        order_number="ORD-0001",
        order_total_minor=1000,
    )
    db_session.add(o1)
    await db_session.flush()

    # Same order number in Org 2 MUST SUCCEED (cross-org unique constraint)
    o2 = Order(
        id=uuid.uuid4(),
        organization_id=org2.id,
        order_number="ORD-0001",
        order_total_minor=2000,
    )
    db_session.add(o2)
    await db_session.flush()
    assert o2.id is not None

    # Duplicate order number in Org 1 MUST FAIL
    o1_dup = Order(
        id=uuid.uuid4(),
        organization_id=org1.id,
        order_number="ORD-0001",
        order_total_minor=3000,
    )
    db_session.add(o1_dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_order_repository_lifecycle_and_snapshots(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Order Repo Org")
    prod = await _create_test_product(db_session, org.id, "PROD-20")

    repo = OrderRepository(db_session, org.id)

    # Sequential order number generation
    num1 = await repo.generate_next_order_number()
    assert num1 == "ORD-0001"

    order = await repo.create_order(
        order_number=num1,
        customer_id=None,
        order_total_minor=50000,
        currency_code="PKR",
        items_data=[
            {
                "product_id": prod.id,
                "product_name_snapshot": prod.name,
                "product_code_snapshot": prod.code,
                "unit_snapshot": prod.base_unit,
                "quantity": 2,
                "unit_price_minor": 25000,
                "line_total_minor": 50000,
            }
        ],
    )
    await db_session.commit()

    # Next number increments
    num2 = await repo.generate_next_order_number()
    assert num2 == "ORD-0002"

    # Query with items
    loaded = await repo.get_order_with_items(order.id)
    assert loaded is not None
    assert loaded.order_number == "ORD-0001"
    assert len(loaded.items) == 1
    assert loaded.items[0].product_name_snapshot == prod.name
    assert loaded.items[0].product_code_snapshot == prod.code
    assert loaded.items[0].unit_snapshot == prod.base_unit

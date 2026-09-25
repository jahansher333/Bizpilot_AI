"""Integration tests for AI deterministic read services (AI-004)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.services import AIDeterministicReadService
from app.modules.customers.models import Customer
from app.modules.dashboard.timezone import DashboardPeriod
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.inventory.models import InventoryBalance
from app.modules.orders.models import Order, OrderItem
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.payments.models import Payment
from app.modules.products.models import Product


async def _create_org(db: AsyncSession, name: str) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        display_name=name,
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db.add(org)
    await db.flush()
    return org


@pytest.mark.asyncio
async def test_ai_sales_summary_and_void_exclusion(db_session: AsyncSession) -> None:
    org_a = await _create_org(db_session, "Sales Org A")
    org_b = await _create_org(db_session, "Sales Org B")

    now = datetime.now(timezone.utc)

    # Org A active order
    order_a1 = Order(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        order_number="ORD-A1",
        status="active",
        ordered_at=now,
        order_total_minor=50000,
        currency_code="PKR",
    )
    # Org A voided order (must be excluded)
    order_a_void = Order(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        order_number="ORD-VOID",
        status="voided",
        ordered_at=now,
        order_total_minor=30000,
        currency_code="PKR",
    )
    # Org B order (tenant isolation)
    order_b = Order(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        order_number="ORD-B1",
        status="active",
        ordered_at=now,
        order_total_minor=99000,
        currency_code="PKR",
    )
    db_session.add_all([order_a1, order_a_void, order_b])
    await db_session.flush()

    res = await AIDeterministicReadService.get_sales_summary(
        session=db_session,
        organization_id=org_a.id,
        period=DashboardPeriod.TODAY,
    )

    assert res.success is True
    assert res.values is not None
    assert res.values.total_sales_minor == 50000
    assert res.values.active_orders_count == 1
    assert "Rs. 500.00" in res.values.total_sales_pkr


@pytest.mark.asyncio
async def test_ai_inventory_status_and_stock_flags(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Stock Org")

    p1 = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code="P-1",
        name="Basmati Rice",
        base_unit="kg",
        default_price_minor=35000,
        currency_code="PKR",
        status="active",
    )
    p2 = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code="P-2",
        name="Cooking Oil",
        base_unit="liter",
        default_price_minor=50000,
        currency_code="PKR",
        status="active",
    )
    db_session.add_all([p1, p2])
    await db_session.flush()

    # p1 has 4 units (low stock <= 10)
    bal1 = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org.id,
        product_id=p1.id,
        on_hand_quantity=4,
    )
    # p2 has 0 units (out of stock)
    bal2 = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org.id,
        product_id=p2.id,
        on_hand_quantity=0,
    )
    db_session.add_all([bal1, bal2])
    await db_session.flush()

    res = await AIDeterministicReadService.get_inventory_status(
        session=db_session,
        organization_id=org.id,
    )

    assert res.success is True
    assert res.values.total_products_tracked == 2
    assert res.values.low_stock_count == 1
    assert res.values.out_of_stock_count == 1

    # Test low_stock_only filter
    res_low = await AIDeterministicReadService.get_inventory_status(
        session=db_session,
        organization_id=org.id,
        low_stock_only=True,
    )
    assert len(res_low.values.items) == 2


@pytest.mark.asyncio
async def test_ai_customer_balance_calculation(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Cust Org")
    cust = Customer(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Kamran Traders",
        phone="+923009998877",
        status="active",
    )
    db_session.add(cust)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Order of 100,000 minor
    order = Order(
        id=uuid.uuid4(),
        organization_id=org.id,
        customer_id=cust.id,
        order_number="ORD-CUST-1",
        status="active",
        ordered_at=now,
        order_total_minor=100000,
        currency_code="PKR",
    )
    # Payment of 60,000 minor
    payment = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        customer_id=cust.id,
        amount_minor=60000,
        channel="cash",
        received_at=now,
        status="active",
    )
    db_session.add_all([order, payment])
    await db_session.flush()

    # Query by ID
    res = await AIDeterministicReadService.get_customer_balance(
        session=db_session,
        organization_id=org.id,
        customer_id=cust.id,
    )
    assert res.success is True
    assert res.values.total_orders_minor == 100000
    assert res.values.total_payments_minor == 60000
    assert res.values.outstanding_balance_minor == 40000
    assert res.values.outstanding_balance_pkr == "Rs. 400.00"

    # Query by name search
    res_search = await AIDeterministicReadService.get_customer_balance(
        session=db_session,
        organization_id=org.id,
        query="Kamran",
    )
    assert res_search.success is True
    assert res_search.values.customer_id == cust.id


@pytest.mark.asyncio
async def test_ai_order_details_and_top_products(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "OrderDetails Org")
    p1 = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code="P-TEA",
        name="Green Tea",
        base_unit="pack",
        default_price_minor=20000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(p1)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    order = Order(
        id=uuid.uuid4(),
        organization_id=org.id,
        order_number="ORD-TEA-101",
        status="active",
        ordered_at=now,
        order_total_minor=40000,
        currency_code="PKR",
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        id=uuid.uuid4(),
        organization_id=org.id,
        order_id=order.id,
        product_id=p1.id,
        product_name_snapshot="Green Tea",
        product_code_snapshot="P-TEA",
        unit_snapshot="pack",
        quantity=2,
        unit_price_minor=20000,
        line_total_minor=40000,
        currency_code="PKR",
    )
    db_session.add(item)
    await db_session.flush()

    # Test order details
    details = await AIDeterministicReadService.get_order_details(
        session=db_session,
        organization_id=org.id,
        order_number="ORD-TEA-101",
    )
    assert details.success is True
    assert details.values.order_total_minor == 40000
    assert len(details.values.items) == 1
    assert details.values.items[0].product_name == "Green Tea"

    # Test top products
    top = await AIDeterministicReadService.get_top_products(
        session=db_session,
        organization_id=org.id,
        period=DashboardPeriod.THIS_MONTH,
        metric="revenue",
    )
    assert top.success is True
    assert len(top.values.items) == 1
    assert top.values.items[0].revenue_minor == 40000
    assert top.values.items[0].quantity_sold == 2


@pytest.mark.asyncio
async def test_ai_expenses_and_payments_breakdowns(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Finance Org")

    cat = ExpenseCategory(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Rent",
        status="active",
    )
    db_session.add(cat)
    await db_session.flush()

    now = datetime.now(timezone.utc)

    exp = Expense(
        id=uuid.uuid4(),
        organization_id=org.id,
        expense_category_id=cat.id,
        amount_minor=150000,
        occurred_at=now,
        status="active",
    )
    pay = Payment(
        id=uuid.uuid4(),
        organization_id=org.id,
        amount_minor=85000,
        channel="bank_transfer",
        received_at=now,
        status="active",
    )
    db_session.add_all([exp, pay])
    await db_session.flush()

    # Expenses summary
    exp_res = await AIDeterministicReadService.get_expense_summary(
        session=db_session,
        organization_id=org.id,
        period=DashboardPeriod.TODAY,
    )
    assert exp_res.success is True
    assert exp_res.values.total_expenses_minor == 150000
    assert len(exp_res.values.categories) == 1
    assert exp_res.values.categories[0].category_name == "Rent"

    # Payments summary
    pay_res = await AIDeterministicReadService.get_payment_summary(
        session=db_session,
        organization_id=org.id,
        period=DashboardPeriod.TODAY,
    )
    assert pay_res.success is True
    assert pay_res.values.total_payments_minor == 85000
    assert len(pay_res.values.channels) == 1
    assert pay_res.values.channels[0].channel == "bank_transfer"

    # Dashboard summary
    dash_res = await AIDeterministicReadService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        period=DashboardPeriod.TODAY,
        role=MemberRole.OWNER,
    )
    assert dash_res.success is True
    assert dash_res.values is not None

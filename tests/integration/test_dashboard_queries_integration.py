"""Integration tests for deterministic dashboard queries (DASH-001)."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.service import DashboardQueryService
from app.modules.dashboard.timezone import DashboardPeriod
from app.modules.expenses.models import Expense
from app.modules.inventory.models import InventoryBalance
from app.modules.orders.models import Order
from app.modules.organizations.models import Organization
from app.modules.payments.models import Payment
from app.modules.products.models import Product


async def _create_test_org(db_session: AsyncSession, name: str = "Dashboard Org") -> Organization:
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
    db_session: AsyncSession, org_id: uuid.UUID, code: str, name: str
) -> Product:
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code=code,
        name=name,
        base_unit="piece",
        default_price_minor=1000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()
    return prod


async def _create_inventory_balance(
    db_session: AsyncSession, org_id: uuid.UUID, prod_id: uuid.UUID, qty: int
) -> InventoryBalance:
    bal = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=prod_id,
        on_hand_quantity=qty,
    )
    db_session.add(bal)
    await db_session.flush()
    return bal


@pytest.mark.asyncio
async def test_deterministic_aggregates_and_void_exclusion(db_session: AsyncSession):
    """Test that active totals match source records and voided/corrected are excluded."""
    org = await _create_test_org(db_session, "Aggregates Org")
    now = datetime.now(timezone.utc)

    # 1. Orders: 2 active (50000, 30000), 1 voided (20000), 1 corrected (10000)
    db_session.add_all([
        Order(
            id=uuid.uuid4(),
            organization_id=org.id,
            order_number=f"ORD-DASH-1-{uuid.uuid4().hex[:4]}",
            order_total_minor=50000,
            status="active",
            ordered_at=now,
        ),
        Order(
            id=uuid.uuid4(),
            organization_id=org.id,
            order_number=f"ORD-DASH-2-{uuid.uuid4().hex[:4]}",
            order_total_minor=30000,
            status="active",
            ordered_at=now,
        ),
        Order(
            id=uuid.uuid4(),
            organization_id=org.id,
            order_number=f"ORD-DASH-VOID-{uuid.uuid4().hex[:4]}",
            order_total_minor=20000,
            status="voided",
            ordered_at=now,
        ),
        Order(
            id=uuid.uuid4(),
            organization_id=org.id,
            order_number=f"ORD-DASH-CORR-{uuid.uuid4().hex[:4]}",
            order_total_minor=10000,
            status="corrected",
            ordered_at=now,
        ),
    ])

    # 2. Payments: 2 active (40000, 30000), 1 voided (15000)
    db_session.add_all([
        Payment(
            id=uuid.uuid4(),
            organization_id=org.id,
            external_reference=f"PAY-DASH-1-{uuid.uuid4().hex[:4]}",
            amount_minor=40000,
            channel="cash",
            status="active",
            received_at=now,
        ),
        Payment(
            id=uuid.uuid4(),
            organization_id=org.id,
            external_reference=f"PAY-DASH-2-{uuid.uuid4().hex[:4]}",
            amount_minor=30000,
            channel="bank_transfer",
            status="active",
            received_at=now,
        ),
        Payment(
            id=uuid.uuid4(),
            organization_id=org.id,
            external_reference=f"PAY-DASH-VOID-{uuid.uuid4().hex[:4]}",
            amount_minor=15000,
            channel="cash",
            status="voided",
            received_at=now,
        ),
    ])

    # 3. Expenses: 2 active (15000, 10000), 1 voided (5000)
    db_session.add_all([
        Expense(
            id=uuid.uuid4(),
            organization_id=org.id,
            amount_minor=15000,
            payment_method="cash",
            status="active",
            occurred_at=now,
            payee="Vendor A",
        ),
        Expense(
            id=uuid.uuid4(),
            organization_id=org.id,
            amount_minor=10000,
            payment_method="bank_transfer",
            status="active",
            occurred_at=now,
            payee="Vendor B",
        ),
        Expense(
            id=uuid.uuid4(),
            organization_id=org.id,
            amount_minor=5000,
            payment_method="cash",
            status="voided",
            occurred_at=now,
            payee="Voided Vendor",
        ),
    ])

    await db_session.flush()

    summary = await DashboardQueryService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        caller_role="owner",
        period=DashboardPeriod.TODAY,
        reference_utc=now,
    )

    # Sales assertions
    assert summary.sales.order_count == 2
    assert summary.sales.total_sales_minor == 80000

    # Payments assertions
    assert summary.payments.payment_count == 2
    assert summary.payments.total_collected_minor == 70000

    # Expenses assertions
    assert summary.expenses is not None
    assert summary.expenses.expense_count == 2
    assert summary.expenses.total_expenses_minor == 25000

    # Net operational cash assertion: 70000 - 25000 = 45000
    assert summary.net_cash is not None
    assert summary.net_cash.net_cash_minor == 45000


@pytest.mark.asyncio
async def test_role_based_filtering_staff_vs_manager(db_session: AsyncSession):
    """Test that Staff gets limited metrics with expenses and net cash redacted."""
    org = await _create_test_org(db_session, "Role Filter Org")
    now = datetime.now(timezone.utc)

    db_session.add(
        Order(
            id=uuid.uuid4(),
            organization_id=org.id,
            order_number=f"ORD-RF-{uuid.uuid4().hex[:4]}",
            order_total_minor=20000,
            status="active",
            ordered_at=now,
        )
    )
    db_session.add(
        Payment(
            id=uuid.uuid4(),
            organization_id=org.id,
            external_reference=f"PAY-RF-{uuid.uuid4().hex[:4]}",
            amount_minor=15000,
            channel="cash",
            status="active",
            received_at=now,
        )
    )
    db_session.add(
        Expense(
            id=uuid.uuid4(),
            organization_id=org.id,
            amount_minor=8000,
            payment_method="cash",
            status="active",
            occurred_at=now,
            payee="Confidential Payee",
        )
    )
    await db_session.flush()

    # Query as Staff
    staff_summary = await DashboardQueryService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        caller_role="staff",
        period=DashboardPeriod.TODAY,
        reference_utc=now,
    )

    assert staff_summary.sales.order_count == 1
    assert staff_summary.sales.total_sales_minor == 20000
    assert staff_summary.payments.payment_count == 1
    assert staff_summary.payments.total_collected_minor == 15000

    # Staff must NOT see expenses or net cash
    assert staff_summary.expenses is None
    assert staff_summary.net_cash is None

    # Recent activity for staff must not contain any expenses
    for item in staff_summary.recent_activity:
        assert item.activity_type != "expense"

    # Query as Manager
    manager_summary = await DashboardQueryService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        caller_role="manager",
        period=DashboardPeriod.TODAY,
        reference_utc=now,
    )

    assert manager_summary.expenses is not None
    assert manager_summary.expenses.total_expenses_minor == 8000
    assert manager_summary.net_cash is not None
    assert manager_summary.net_cash.net_cash_minor == 7000  # 15000 - 8000
    assert any(item.activity_type == "expense" for item in manager_summary.recent_activity)


@pytest.mark.asyncio
async def test_cross_tenant_isolation(db_session: AsyncSession):
    """Test that metrics strictly aggregate within organization boundaries."""
    org_a = await _create_test_org(db_session, "Tenant A")
    org_b = await _create_test_org(db_session, "Tenant B")
    now = datetime.now(timezone.utc)

    # Org A records
    db_session.add(
        Order(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            order_number=f"ORD-A-{uuid.uuid4().hex[:4]}",
            order_total_minor=10000,
            status="active",
            ordered_at=now,
        )
    )
    db_session.add(
        Payment(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            external_reference=f"PAY-A-{uuid.uuid4().hex[:4]}",
            amount_minor=10000,
            channel="cash",
            status="active",
            received_at=now,
        )
    )

    # Org B records (much larger amounts)
    db_session.add(
        Order(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            order_number=f"ORD-B-{uuid.uuid4().hex[:4]}",
            order_total_minor=900000,
            status="active",
            ordered_at=now,
        )
    )
    db_session.add(
        Payment(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            external_reference=f"PAY-B-{uuid.uuid4().hex[:4]}",
            amount_minor=900000,
            channel="cash",
            status="active",
            received_at=now,
        )
    )
    await db_session.flush()

    summary_a = await DashboardQueryService.get_dashboard_summary(
        session=db_session,
        organization_id=org_a.id,
        caller_role="owner",
        period=DashboardPeriod.TODAY,
        reference_utc=now,
    )

    assert summary_a.sales.total_sales_minor == 10000
    assert summary_a.payments.total_collected_minor == 10000
    for act in summary_a.recent_activity:
        assert "ORD-B" not in act.reference_code
        assert "PAY-B" not in act.reference_code


@pytest.mark.asyncio
async def test_low_stock_indicators(db_session: AsyncSession):
    """Test low-stock products are detected when on-hand <= threshold."""
    org = await _create_test_org(db_session, "Stock Org")
    now = datetime.now(timezone.utc)

    p1 = await _create_product(db_session, org.id, f"SKU-LOW-1-{uuid.uuid4().hex[:4]}", "Sugar 1kg")
    p2 = await _create_product(db_session, org.id, f"SKU-OUT-2-{uuid.uuid4().hex[:4]}", "Tea 500g")
    p3 = await _create_product(db_session, org.id, f"SKU-OK-3-{uuid.uuid4().hex[:4]}", "Flour 5kg")

    await _create_inventory_balance(db_session, org.id, p1.id, qty=5)   # Low stock (<= 10)
    await _create_inventory_balance(db_session, org.id, p2.id, qty=0)   # Out of stock (<= 0)
    await _create_inventory_balance(db_session, org.id, p3.id, qty=50)  # Adequate stock (> 10)

    summary = await DashboardQueryService.get_dashboard_summary(
        session=db_session,
        organization_id=org.id,
        caller_role="owner",
        period=DashboardPeriod.TODAY,
        low_stock_threshold=10,
        reference_utc=now,
    )

    assert summary.inventory.low_stock_count == 2
    item_codes = {item.product_code for item in summary.inventory.items}
    assert p1.code in item_codes
    assert p2.code in item_codes
    assert p3.code not in item_codes

    p2_item = next(i for i in summary.inventory.items if i.product_code == p2.code)
    assert p2_item.is_out_of_stock is True

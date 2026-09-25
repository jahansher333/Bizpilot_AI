"""PostgreSQL integration tests for Expense categories and Expenses persistence (EXP-001)."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException, ValidationException
from app.modules.auth.models import User
from app.modules.expenses.enums import ExpenseCategoryStatus, ExpensePaymentMethod, ExpenseStatus
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.repository import ExpenseCategoryRepository, ExpenseRepository
from app.modules.organizations.models import Organization


async def _create_test_org(db_session: AsyncSession, name: str = "Expense Org") -> Organization:
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


async def _create_test_user(db_session: AsyncSession, email_prefix: str = "expenser") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Expense User",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_valid_expense_category_persistence_and_uniqueness(db_session: AsyncSession):
    """Test valid category creation, active name uniqueness in org, and name reuse across orgs."""
    org1 = await _create_test_org(db_session, "Org 1")
    org2 = await _create_test_org(db_session, "Org 2")

    cat_repo = ExpenseCategoryRepository(db_session)

    # Create category in Org 1
    cat1 = await cat_repo.create(org1.id, "Utilities")
    assert cat1.id is not None
    assert cat1.organization_id == org1.id
    assert cat1.name == "Utilities"
    assert cat1.status == ExpenseCategoryStatus.ACTIVE.value

    # Duplicate active name in same org must be rejected with ConflictException
    with pytest.raises(ConflictException):
        await cat_repo.create(org1.id, "Utilities")

    # Same active name in different org is allowed
    cat2 = await cat_repo.create(org2.id, "Utilities")
    assert cat2.id is not None
    assert cat2.organization_id == org2.id

    # Archiving category in Org 1 allows new category with same name in Org 1
    await cat_repo.archive(org1.id, cat1.id)
    cat3 = await cat_repo.create(org1.id, "Utilities")
    assert cat3.id != cat1.id
    assert cat3.status == ExpenseCategoryStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_valid_expense_persistence(db_session: AsyncSession):
    """Test standard operational expense recording with optional category and user."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    cat_repo = ExpenseCategoryRepository(db_session)
    category = await cat_repo.create(org.id, "Office Supplies")

    expense_repo = ExpenseRepository(db_session)
    expense = await expense_repo.create(
        organization_id=org.id,
        amount_minor=125000,  # Rs. 1250.00
        expense_category_id=category.id,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Stationery Mart",
        description="Printer paper and pens",
        currency_code="PKR",
        created_by_user_id=user.id,
    )

    assert expense.id is not None
    assert expense.organization_id == org.id
    assert expense.amount_minor == 125000
    assert expense.expense_category_id == category.id
    assert expense.status == ExpenseStatus.ACTIVE.value
    assert expense.currency_code == "PKR"
    assert expense.created_by_user_id == user.id

    # Verify query through session
    fetched = await expense_repo.get_by_id(org.id, expense.id)
    assert fetched is not None
    assert fetched.payee == "Stationery Mart"


@pytest.mark.asyncio
async def test_expense_monetary_check_constraint(db_session: AsyncSession):
    """Test PostgreSQL CHECK (amount_minor > 0) rejects non-positive amounts."""
    org = await _create_test_org(db_session)

    # 1. Zero amount
    with pytest.raises(IntegrityError) as exc_info:
        exp_zero = Expense(
            organization_id=org.id,
            amount_minor=0,
            currency_code="PKR",
            payment_method="cash",
            status="active",
        )
        db_session.add(exp_zero)
        await db_session.flush()
    assert "check_expenses_amount_positive" in str(exc_info.value)
    await db_session.rollback()

    # 2. Negative amount
    with pytest.raises(IntegrityError) as exc_info:
        exp_neg = Expense(
            organization_id=org.id,
            amount_minor=-5000,
            currency_code="PKR",
            payment_method="cash",
            status="active",
        )
        db_session.add(exp_neg)
        await db_session.flush()
    assert "check_expenses_amount_positive" in str(exc_info.value)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_cross_organization_category_rejection_at_database_level(db_session: AsyncSession):
    """Test trg_expenses_tenant_consistency rejects associating category from Org B to Org A."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    cat_b = ExpenseCategory(
        organization_id=org_b.id,
        name="Org B Category",
        status=ExpenseCategoryStatus.ACTIVE.value,
    )
    db_session.add(cat_b)
    await db_session.flush()

    # Attempt to insert expense in Org A referencing category of Org B directly via raw model
    with pytest.raises(IntegrityError) as exc_info:
        cross_expense = Expense(
            organization_id=org_a.id,
            expense_category_id=cat_b.id,  # Cross-tenant reference
            amount_minor=50000,
            currency_code="PKR",
            payment_method="cash",
            status="active",
        )
        db_session.add(cross_expense)
        await db_session.flush()

    assert "Cross-tenant violation: expense_category does not belong to organization" in str(exc_info.value)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_repository_list_and_daily_totals(db_session: AsyncSession):
    """Test repository listing, category filtering, and daily total calculations."""
    org = await _create_test_org(db_session)
    cat_repo = ExpenseCategoryRepository(db_session)
    exp_repo = ExpenseRepository(db_session)

    cat1 = await cat_repo.create(org.id, "Rent")
    cat2 = await cat_repo.create(org.id, "Tea & Refreshments")

    now = datetime.now(timezone.utc)
    today = now.date()

    e1 = await exp_repo.create(
        organization_id=org.id,
        amount_minor=100000,
        expense_category_id=cat1.id,
        occurred_at=now,
    )
    e2 = await exp_repo.create(
        organization_id=org.id,
        amount_minor=20000,
        expense_category_id=cat2.id,
        occurred_at=now,
    )

    # List all
    items, total = await exp_repo.list(org.id)
    assert total == 2
    assert len(items) == 2

    # Filter by category
    cat1_items, cat1_total = await exp_repo.list(org.id, category_id=cat1.id)
    assert cat1_total == 1
    assert cat1_items[0].id == e1.id

    # Daily total
    daily_sum, count = await exp_repo.get_daily_total(org.id, today)
    assert daily_sum == 120000  # 100000 + 20000
    assert count == 2

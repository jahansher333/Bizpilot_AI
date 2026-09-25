"""Integration tests for ExpenseService, idempotency, void, and correction (EXP-002)."""

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
from app.modules.auth.models import User
from app.modules.expenses.enums import ExpenseCategoryStatus, ExpensePaymentMethod, ExpenseStatus
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.schemas import (
    ExpenseCategoryCreateDTO,
    ExpenseCategoryUpdateDTO,
    ExpenseCorrectDTO,
    ExpenseCreateDTO,
    ExpenseVoidDTO,
)
from app.modules.expenses.service import ExpenseService
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.trace.enums import TraceAction
from app.modules.trace.models import InternalTraceEvent


async def _create_test_org(db_session: AsyncSession, name: str = "Service Org") -> Organization:
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


async def _create_test_user(db_session: AsyncSession, email_prefix: str = "service_user") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name="Service User",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_record_expense_happy_path_and_roles(db_session: AsyncSession):
    """Test expense creation with Owner, Manager, and denial for Staff."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    service = ExpenseService(db_session, org.id)

    # 1. Owner can record expense
    exp_in_owner = ExpenseCreateDTO(
        amount_minor=50000,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Utility Provider",
        description="Electricity Bill",
    )
    exp_owner = await service.record_expense(exp_in_owner, user.id, MemberRole.OWNER)
    assert exp_owner.id is not None
    assert exp_owner.amount_minor == 50000
    assert exp_owner.status == ExpenseStatus.ACTIVE.value

    # 2. Manager can record expense
    exp_in_mgr = ExpenseCreateDTO(
        amount_minor=15000,
        payment_method=ExpensePaymentMethod.BANK_TRANSFER,
        payee="Internet Provider",
        description="Fiber Bill",
    )
    exp_mgr = await service.record_expense(exp_in_mgr, user.id, MemberRole.MANAGER)
    assert exp_mgr.id is not None
    assert exp_mgr.amount_minor == 15000

    # 3. Staff is denied
    exp_in_staff = ExpenseCreateDTO(
        amount_minor=2000,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Tea Stall",
    )
    with pytest.raises(AuthorizationException):
        await service.record_expense(exp_in_staff, user.id, MemberRole.STAFF)


@pytest.mark.asyncio
async def test_expense_idempotency_safe_replay_and_conflict(db_session: AsyncSession):
    """Test retry-safe replay with identical payload and conflict rejection with changed payload."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    service = ExpenseService(db_session, org.id)
    idem_key = f"idem-exp-{uuid.uuid4().hex}"

    exp_in = ExpenseCreateDTO(
        amount_minor=80000,
        payment_method=ExpensePaymentMethod.CHEQUE,
        payee="Office Landlord",
        description="Partial rent",
    )

    # First attempt: records new expense
    exp1 = await service.record_expense(exp_in, user.id, MemberRole.OWNER, idempotency_key=idem_key)
    await db_session.commit()

    # Second attempt (same key + same payload): safe replay
    exp2 = await service.record_expense(exp_in, user.id, MemberRole.OWNER, idempotency_key=idem_key)
    assert exp2.id == exp1.id
    assert exp2.amount_minor == 80000

    # Third attempt (same key + different payload): ConflictException
    exp_in_diff = ExpenseCreateDTO(
        amount_minor=95000,  # Changed amount
        payment_method=ExpensePaymentMethod.CHEQUE,
        payee="Office Landlord",
        description="Partial rent",
    )
    with pytest.raises(ConflictException):
        await service.record_expense(exp_in_diff, user.id, MemberRole.OWNER, idempotency_key=idem_key)


@pytest.mark.asyncio
async def test_void_expense_lifecycle_and_rbac(db_session: AsyncSession):
    """Test voiding expense (Owner only), denial for Manager/Staff, and trace event."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    service = ExpenseService(db_session, org.id)

    exp_in = ExpenseCreateDTO(
        amount_minor=45000,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Supplier",
        description="Duplicate entry",
    )
    expense = await service.record_expense(exp_in, user.id, MemberRole.OWNER)

    # 1. Staff and Manager cannot void
    with pytest.raises(AuthorizationException):
        await service.void_expense(expense.id, ExpenseVoidDTO(reason="Mistake"), user.id, MemberRole.STAFF)

    with pytest.raises(AuthorizationException):
        await service.void_expense(expense.id, ExpenseVoidDTO(reason="Mistake"), user.id, MemberRole.MANAGER)

    # 2. Owner can void
    voided = await service.void_expense(
        expense.id,
        ExpenseVoidDTO(reason="Duplicate voucher recorded by mistake"),
        user.id,
        MemberRole.OWNER,
    )
    assert voided.status == ExpenseStatus.VOIDED.value
    assert voided.voided_at is not None
    assert "[VOIDED: Duplicate voucher recorded by mistake]" in voided.description

    # 3. Verify internal trace event was recorded
    stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.target_id == expense.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_VOIDED.value,
    )
    trace = await db_session.scalar(stmt)
    assert trace is not None
    assert trace.organization_id == org.id

    # 4. Re-voiding raises ValidationException
    with pytest.raises(ValidationException):
        await service.void_expense(expense.id, ExpenseVoidDTO(reason="Again"), user.id, MemberRole.OWNER)


@pytest.mark.asyncio
async def test_correct_expense_lifecycle_and_rbac(db_session: AsyncSession):
    """Test correcting expense (Owner and Manager), denial for Staff, replacement links, and trace event."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    service = ExpenseService(db_session, org.id)

    exp_in = ExpenseCreateDTO(
        amount_minor=30000,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Repair Service",
        description="AC maintenance",
    )
    original = await service.record_expense(exp_in, user.id, MemberRole.OWNER)

    # 1. Staff cannot correct
    corr_in = ExpenseCorrectDTO(
        reason="Invoice was for 35000 not 30000",
        amount_minor=35000,
        payment_method=ExpensePaymentMethod.CASH,
        payee="Repair Service",
    )
    with pytest.raises(AuthorizationException):
        await service.correct_expense(original.id, corr_in, user.id, MemberRole.STAFF)

    # 2. Manager can correct
    replacement = await service.correct_expense(original.id, corr_in, user.id, MemberRole.MANAGER)
    assert replacement.id is not None
    assert replacement.id != original.id
    assert replacement.amount_minor == 35000
    assert replacement.status == ExpenseStatus.ACTIVE.value
    assert replacement.corrects_expense_id == original.id

    # Refresh original
    await db_session.refresh(original)
    assert original.status == ExpenseStatus.CORRECTED.value
    assert original.replaced_by_expense_id == replacement.id

    # 3. Verify internal trace event was recorded
    stmt = select(InternalTraceEvent).where(
        InternalTraceEvent.target_id == original.id,
        InternalTraceEvent.action == TraceAction.FINANCE_RECORD_CORRECTED.value,
    )
    trace = await db_session.scalar(stmt)
    assert trace is not None
    assert trace.event_metadata["replacement_amount_minor"] == 35000

    # 4. Cannot void or re-correct already corrected expense
    with pytest.raises(ValidationException):
        await service.correct_expense(original.id, corr_in, user.id, MemberRole.OWNER)

    with pytest.raises(ValidationException):
        await service.void_expense(original.id, ExpenseVoidDTO(reason="Try void"), user.id, MemberRole.OWNER)


@pytest.mark.asyncio
async def test_category_lifecycle_and_validation(db_session: AsyncSession):
    """Test category creation, updating, archiving, and preventing assignment of archived categories."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session)

    service = ExpenseService(db_session, org.id)

    # 1. Staff cannot create categories
    with pytest.raises(AuthorizationException):
        await service.create_category(ExpenseCategoryCreateDTO(name="Travel"), MemberRole.STAFF)

    # 2. Manager can create category
    cat = await service.create_category(ExpenseCategoryCreateDTO(name="Travel"), MemberRole.MANAGER)
    assert cat.name == "Travel"
    assert cat.status == ExpenseCategoryStatus.ACTIVE.value

    # 3. Manager can update category name
    updated_cat = await service.update_category(
        cat.id,
        ExpenseCategoryUpdateDTO(name="Travel & Fuel"),
        MemberRole.MANAGER,
    )
    assert updated_cat.name == "Travel & Fuel"

    # 4. Archive category
    archived_cat = await service.archive_category(cat.id, MemberRole.MANAGER)
    assert archived_cat.status == ExpenseCategoryStatus.ARCHIVED.value

    # 5. Recording expense against archived category is rejected
    exp_in = ExpenseCreateDTO(
        amount_minor=10000,
        expense_category_id=archived_cat.id,
    )
    with pytest.raises(ValidationException) as exc_info:
        await service.record_expense(exp_in, user.id, MemberRole.MANAGER)
    assert "archived" in str(exc_info.value).lower()

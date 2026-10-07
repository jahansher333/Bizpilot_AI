"""Database repository for tenant-scoped expenses and categories (EXP-001)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.modules.dashboard.timezone import get_zone_info
from app.modules.expenses.enums import ExpenseCategoryStatus, ExpensePaymentMethod, ExpenseStatus
from app.modules.expenses.models import Expense, ExpenseCategory


class ExpenseCategoryRepository:
    """Repository handling database operations for expense categories."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> ExpenseCategory | None:
        """Fetch a category by ID within a specific organization."""
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_name(
        self,
        organization_id: uuid.UUID,
        name: str,
        status: ExpenseCategoryStatus = ExpenseCategoryStatus.ACTIVE,
    ) -> ExpenseCategory | None:
        """Fetch a category by name and status within an organization."""
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.organization_id == organization_id,
            func.lower(ExpenseCategory.name) == func.lower(name.strip()),
            ExpenseCategory.status == status.value,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        organization_id: uuid.UUID,
        name: str,
    ) -> ExpenseCategory:
        """Create a new expense category ensuring active name uniqueness."""
        trimmed_name = name.strip()
        existing = await self.get_by_name(organization_id, trimmed_name, ExpenseCategoryStatus.ACTIVE)
        if existing:
            raise ConflictException(f"Active expense category '{trimmed_name}' already exists in this organization")

        category = ExpenseCategory(
            organization_id=organization_id,
            name=trimmed_name,
            status=ExpenseCategoryStatus.ACTIVE.value,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def update_name(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID,
        new_name: str,
    ) -> ExpenseCategory:
        """Update an active expense category name."""
        category = await self.get_by_id(organization_id, category_id)
        if not category:
            raise NotFoundException("Expense category not found")

        trimmed_name = new_name.strip()
        existing = await self.get_by_name(organization_id, trimmed_name, ExpenseCategoryStatus.ACTIVE)
        if existing and existing.id != category.id:
            raise ConflictException(f"Active expense category '{trimmed_name}' already exists in this organization")

        category.name = trimmed_name
        await self.session.flush()
        return category

    async def archive(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> ExpenseCategory:
        """Archive an expense category."""
        category = await self.get_by_id(organization_id, category_id)
        if not category:
            raise NotFoundException("Expense category not found")

        category.status = ExpenseCategoryStatus.ARCHIVED.value
        await self.session.flush()
        return category

    async def list(
        self,
        organization_id: uuid.UUID,
        status: ExpenseCategoryStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[ExpenseCategory], int]:
        """List categories with optional status filter and pagination."""
        base_filters = [ExpenseCategory.organization_id == organization_id]
        if status:
            base_filters.append(ExpenseCategory.status == status.value)

        count_stmt = select(func.count(ExpenseCategory.id)).where(and_(*base_filters))
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        list_stmt = (
            select(ExpenseCategory)
            .where(and_(*base_filters))
            .order_by(ExpenseCategory.name.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(list_stmt)
        items = result.scalars().all()

        return items, total


class ExpenseRepository:
    """Repository handling database operations for recorded operational expenses."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> Expense | None:
        """Fetch an expense by ID ensuring strict tenant scoping."""
        stmt = select(Expense).where(
            Expense.id == expense_id,
            Expense.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        organization_id: uuid.UUID,
        amount_minor: int,
        expense_category_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
        payment_method: ExpensePaymentMethod = ExpensePaymentMethod.CASH,
        payee: str | None = None,
        description: str | None = None,
        currency_code: str = "PKR",
        created_by_user_id: uuid.UUID | None = None,
        corrects_expense_id: uuid.UUID | None = None,
    ) -> Expense:
        """Create a new expense record."""
        if expense_category_id:
            cat_stmt = select(ExpenseCategory).where(
                ExpenseCategory.id == expense_category_id,
                ExpenseCategory.organization_id == organization_id,
            )
            cat_res = await self.session.execute(cat_stmt)
            category = cat_res.scalars().first()
            if not category:
                raise ValidationException("Referenced expense category does not exist in this organization")

        expense = Expense(
            organization_id=organization_id,
            expense_category_id=expense_category_id,
            amount_minor=amount_minor,
            currency_code=currency_code,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            payment_method=payment_method.value if isinstance(payment_method, ExpensePaymentMethod) else payment_method,
            payee=payee.strip() if payee else None,
            description=description.strip() if description else None,
            status=ExpenseStatus.ACTIVE.value,
            created_by_user_id=created_by_user_id,
            corrects_expense_id=corrects_expense_id,
        )
        self.session.add(expense)
        await self.session.flush()
        return expense

    async def list(
        self,
        organization_id: uuid.UUID,
        status: ExpenseStatus | None = None,
        category_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
        timezone_name: str | None = None,
    ) -> tuple[Sequence[Expense], int]:
        """List expenses with optional filters and pagination.

        start_date and end_date are calendar days in the business timezone (Asia/Karachi by default).
        """
        tz = get_zone_info(timezone_name)
        base_filters = [Expense.organization_id == organization_id]

        if status:
            base_filters.append(Expense.status == status.value)
        if category_id:
            base_filters.append(Expense.expense_category_id == category_id)
        if start_date:
            start_dt = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
            base_filters.append(Expense.occurred_at >= start_dt)
        if end_date:
            end_dt = datetime.combine(end_date, time.max, tzinfo=tz).astimezone(timezone.utc)
            base_filters.append(Expense.occurred_at <= end_dt)

        count_stmt = select(func.count(Expense.id)).where(and_(*base_filters))
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        list_stmt = (
            select(Expense)
            .where(and_(*base_filters))
            .order_by(Expense.occurred_at.desc(), Expense.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(list_stmt)
        items = result.scalars().all()

        return items, total

    async def get_daily_total(
        self,
        organization_id: uuid.UUID,
        target_date: date,
        timezone_name: str | None = None,
    ) -> tuple[int, int]:
        """Calculate total amount_minor and count of active expenses for a business-timezone day."""
        tz = get_zone_info(timezone_name)
        start_dt = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(timezone.utc)
        end_dt = datetime.combine(target_date, time.max, tzinfo=tz).astimezone(timezone.utc)

        stmt = select(
            func.coalesce(func.sum(Expense.amount_minor), 0),
            func.count(Expense.id),
        ).where(
            Expense.organization_id == organization_id,
            Expense.status == ExpenseStatus.ACTIVE.value,
            Expense.occurred_at >= start_dt,
            Expense.occurred_at <= end_dt,
        )
        result = await self.session.execute(stmt)
        total_minor, count = result.one()
        return int(total_minor), int(count)

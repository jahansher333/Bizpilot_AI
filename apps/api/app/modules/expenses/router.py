"""FastAPI routers for tenant-scoped expense categories and expense endpoints (EXP-003)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.expenses.enums import ExpenseCategoryStatus, ExpensePaymentMethod, ExpenseStatus
from app.modules.expenses.schemas import (
    DailyExpenseTotalDTO,
    ExpenseCategoryCreateDTO,
    ExpenseCategoryListResponseDTO,
    ExpenseCategoryResponseDTO,
    ExpenseCategoryUpdateDTO,
    ExpenseCorrectDTO,
    ExpenseCreateDTO,
    ExpenseListResponseDTO,
    ExpenseResponseDTO,
    ExpenseVoidDTO,
)
from app.modules.dashboard.timezone import get_zone_info
from app.modules.expenses.service import ExpenseService
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

# 1. Expense Categories Router
category_router = APIRouter(
    prefix="/organizations/{organization_id}/expense-categories",
    tags=["expense-categories"],
)


@category_router.post(
    "",
    response_model=ExpenseCategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create expense category",
    description="Creates a new active expense category. Requires expenses:create permission.",
)
async def create_expense_category(
    organization_id: uuid.UUID,
    request: ExpenseCategoryCreateDTO,
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseCategoryResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    category = await service.create_category(request, context.role)
    await session.commit()
    return ExpenseCategoryResponseDTO.model_validate(category)


@category_router.get(
    "",
    response_model=ExpenseCategoryListResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="List expense categories",
    description="Lists expense categories with optional status filter. Requires expenses:read permission.",
)
async def list_expense_categories(
    organization_id: uuid.UUID,
    status: Optional[ExpenseCategoryStatus] = Query(None, description="Optional status filter: 'active', 'archived'"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_READ)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseCategoryListResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    items, total = await service.list_categories(context.role, status=status, limit=limit, offset=offset)
    return ExpenseCategoryListResponseDTO(
        items=[ExpenseCategoryResponseDTO.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@category_router.get(
    "/{category_id}",
    response_model=ExpenseCategoryResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get expense category",
    description="Retrieves a single expense category by ID. Requires expenses:read permission.",
)
async def get_expense_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_READ)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseCategoryResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    category = await service.get_category(category_id, context.role)
    return ExpenseCategoryResponseDTO.model_validate(category)


@category_router.put(
    "/{category_id}",
    response_model=ExpenseCategoryResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Update expense category",
    description="Updates the name of an active expense category. Requires expenses:correct permission.",
)
async def update_expense_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    request: ExpenseCategoryUpdateDTO,
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_CORRECT)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseCategoryResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    category = await service.update_category(category_id, request, context.role)
    await session.commit()
    return ExpenseCategoryResponseDTO.model_validate(category)


@category_router.post(
    "/{category_id}/archive",
    response_model=ExpenseCategoryResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Archive expense category",
    description="Archives an expense category. Requires expenses:correct permission.",
)
async def archive_expense_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_CORRECT)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseCategoryResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    category = await service.archive_category(category_id, context.role)
    await session.commit()
    return ExpenseCategoryResponseDTO.model_validate(category)


# 2. Expenses Router
expense_router = APIRouter(
    prefix="/organizations/{organization_id}/expenses",
    tags=["expenses"],
)


@expense_router.post(
    "",
    response_model=ExpenseResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Record expense",
    description="Records an operational expense. Supports idempotency via Idempotency-Key. Requires expenses:create permission.",
)
async def record_expense(
    organization_id: uuid.UUID,
    request: ExpenseCreateDTO,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    expense = await service.record_expense(
        expense_in=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return ExpenseResponseDTO.model_validate(expense)


@expense_router.get(
    "",
    response_model=ExpenseListResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="List expenses",
    description="Lists expenses with optional filters and pagination. Requires expenses:read permission.",
)
async def list_expenses(
    organization_id: uuid.UUID,
    status: Optional[ExpenseStatus] = Query(None, description="Optional status filter"),
    category_id: Optional[uuid.UUID] = Query(None, description="Optional category filter"),
    start_date: Optional[date] = Query(None, description="Optional start date"),
    end_date: Optional[date] = Query(None, description="Optional end date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_READ)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseListResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    items, total = await service.list_expenses(
        actor_role=context.role,
        status=status,
        category_id=category_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        timezone_name=context.organization.timezone,
    )
    return ExpenseListResponseDTO(
        items=[ExpenseResponseDTO.model_validate(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@expense_router.get(
    "/daily-total",
    response_model=DailyExpenseTotalDTO,
    status_code=status.HTTP_200_OK,
    summary="Get daily expense total",
    description="Returns aggregate total of active expenses for a target date. Requires expenses:read permission.",
)
async def get_daily_total(
    organization_id: uuid.UUID,
    target_date: Optional[date] = Query(None, description="Target date in the business timezone (defaults to today there)"),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_READ)),
    session: AsyncSession = Depends(get_session),
) -> DailyExpenseTotalDTO:
    from datetime import timezone, datetime
    tz = get_zone_info(context.organization.timezone)
    service = ExpenseService(session=session, organization_id=context.organization_id)
    effective_date = target_date or datetime.now(timezone.utc).astimezone(tz).date()
    return await service.get_daily_expense_total(effective_date, context.role, tz.key)


@expense_router.get(
    "/{expense_id}",
    response_model=ExpenseResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get expense",
    description="Retrieves a single expense by ID. Requires expenses:read permission.",
)
async def get_expense(
    organization_id: uuid.UUID,
    expense_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_READ)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    expense = await service.get_expense(expense_id, context.role)
    return ExpenseResponseDTO.model_validate(expense)


@expense_router.post(
    "/{expense_id}/void",
    response_model=ExpenseResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Void expense",
    description="Voids an active expense with mandatory reason. Owner only operation. Requires expenses:void permission.",
)
async def void_expense(
    organization_id: uuid.UUID,
    expense_id: uuid.UUID,
    request: ExpenseVoidDTO,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_VOID)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    expense = await service.void_expense(
        expense_id=expense_id,
        void_data=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return ExpenseResponseDTO.model_validate(expense)


@expense_router.post(
    "/{expense_id}/correct",
    response_model=ExpenseResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Correct expense",
    description="Corrects an active expense by issuing an auditable replacement. Requires expenses:correct permission.",
)
async def correct_expense(
    organization_id: uuid.UUID,
    expense_id: uuid.UUID,
    request: ExpenseCorrectDTO,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.EXPENSES_CORRECT)),
    session: AsyncSession = Depends(get_session),
) -> ExpenseResponseDTO:
    service = ExpenseService(session=session, organization_id=context.organization_id)
    replacement = await service.correct_expense(
        expense_id=expense_id,
        correction_data=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return ExpenseResponseDTO.model_validate(replacement)

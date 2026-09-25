"""Domain service for managing expenses, idempotency, void, and correction (EXP-002)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.idempotency.service import IdempotencyService, compute_request_hash
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.expenses.enums import ExpenseCategoryStatus, ExpensePaymentMethod, ExpenseStatus
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.repository import ExpenseCategoryRepository, ExpenseRepository
from app.modules.expenses.schemas import (
    DailyExpenseTotalDTO,
    ExpenseCategoryCreateDTO,
    ExpenseCategoryResponseDTO,
    ExpenseCategoryUpdateDTO,
    ExpenseCorrectDTO,
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    ExpenseVoidDTO,
)
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.service import InternalTraceService


class ExpenseService:
    """Domain service managing operational expenses and categories."""

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        idempotency_service: Optional[IdempotencyService] = None,
        trace_service: Optional[InternalTraceService] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._category_repo = ExpenseCategoryRepository(session)
        self._expense_repo = ExpenseRepository(session)
        self._idempotency_service = idempotency_service or IdempotencyService(session)
        self._trace_service = trace_service or InternalTraceService(session, organization_id)

    # ---------------------------------------------------------
    # Category Operations
    # ---------------------------------------------------------

    async def create_category(
        self,
        category_in: ExpenseCategoryCreateDTO,
        actor_role: str | MemberRole,
    ) -> ExpenseCategory:
        """Create a new expense category within the organization."""
        check_permission(actor_role, Permission.EXPENSES_CREATE)
        return await self._category_repo.create(self._organization_id, category_in.name)

    async def update_category(
        self,
        category_id: uuid.UUID,
        category_in: ExpenseCategoryUpdateDTO,
        actor_role: str | MemberRole,
    ) -> ExpenseCategory:
        """Update an active expense category name."""
        check_permission(actor_role, Permission.EXPENSES_CORRECT)
        return await self._category_repo.update_name(self._organization_id, category_id, category_in.name)

    async def archive_category(
        self,
        category_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> ExpenseCategory:
        """Archive an expense category."""
        check_permission(actor_role, Permission.EXPENSES_CORRECT)
        return await self._category_repo.archive(self._organization_id, category_id)

    async def get_category(
        self,
        category_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> ExpenseCategory:
        """Retrieve category by ID with tenant scoping and RBAC."""
        check_permission(actor_role, Permission.EXPENSES_READ)
        cat = await self._category_repo.get_by_id(self._organization_id, category_id)
        if not cat:
            raise NotFoundException("Expense category not found")
        return cat

    async def list_categories(
        self,
        actor_role: str | MemberRole,
        status: ExpenseCategoryStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[ExpenseCategory], int]:
        """List expense categories with optional status filter."""
        check_permission(actor_role, Permission.EXPENSES_READ)
        return await self._category_repo.list(
            self._organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    # ---------------------------------------------------------
    # Expense Recording & Idempotency
    # ---------------------------------------------------------

    async def record_expense(
        self,
        expense_in: ExpenseCreateDTO,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
        idempotency_key: Optional[str] = None,
    ) -> Expense:
        """Record an operational expense.

        Enforces RBAC, positive integer amount, valid category reference,
        and retry-safe idempotency.
        """
        check_permission(actor_role, Permission.EXPENSES_CREATE)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            req_hash = compute_request_hash(expense_in)
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:record",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                resp = ExpenseResponseDTO.model_validate_json(payload_str)
                existing = await self._expense_repo.get_by_id(self._organization_id, resp.id)
                if existing is not None:
                    return existing

        if expense_in.amount_minor <= 0:
            raise ValidationException("Expense amount must be greater than zero")

        if len(expense_in.currency_code) != 3:
            raise ValidationException("Currency code must be exactly 3 characters")

        # Validate category if provided
        if expense_in.expense_category_id:
            category = await self._category_repo.get_by_id(
                self._organization_id,
                expense_in.expense_category_id,
            )
            if not category:
                raise ValidationException("Referenced expense category does not exist in this organization")
            if category.status != ExpenseCategoryStatus.ACTIVE.value:
                raise ValidationException("Cannot assign an archived expense category to a new expense")

        expense = await self._expense_repo.create(
            organization_id=self._organization_id,
            amount_minor=expense_in.amount_minor,
            expense_category_id=expense_in.expense_category_id,
            occurred_at=expense_in.occurred_at,
            payment_method=expense_in.payment_method,
            payee=expense_in.payee,
            description=expense_in.description,
            currency_code=expense_in.currency_code,
            created_by_user_id=actor_user_id,
        )

        if clean_key and req_hash:
            resp_dto = ExpenseResponseDTO.model_validate(expense)
            await self._idempotency_service.record_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:record",
                idempotency_key=clean_key,
                request_hash=req_hash,
                response_code=201,
                response_payload=resp_dto.model_dump_json(),
            )

        return expense

    # ---------------------------------------------------------
    # Expense Retrieval & Listing
    # ---------------------------------------------------------

    async def get_expense(
        self,
        expense_id: uuid.UUID,
        actor_role: str | MemberRole,
    ) -> Expense:
        """Fetch expense by ID with tenant isolation and RBAC."""
        check_permission(actor_role, Permission.EXPENSES_READ)
        expense = await self._expense_repo.get_by_id(self._organization_id, expense_id)
        if not expense:
            raise NotFoundException("Expense not found")
        return expense

    async def list_expenses(
        self,
        actor_role: str | MemberRole,
        status: ExpenseStatus | None = None,
        category_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[Expense], int]:
        """List expenses with optional filters and pagination."""
        check_permission(actor_role, Permission.EXPENSES_READ)
        return await self._expense_repo.list(
            organization_id=self._organization_id,
            status=status,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    async def get_daily_expense_total(
        self,
        target_date: date,
        actor_role: str | MemberRole,
    ) -> DailyExpenseTotalDTO:
        """Fetch active daily expense total for dashboard/reporting."""
        check_permission(actor_role, Permission.EXPENSES_READ)
        total_minor, count = await self._expense_repo.get_daily_total(self._organization_id, target_date)
        return DailyExpenseTotalDTO(
            date=target_date.isoformat(),
            total_minor=total_minor,
            expense_count=count,
            currency_code="PKR",
        )

    # ---------------------------------------------------------
    # Void and Correction Operations
    # ---------------------------------------------------------

    async def void_expense(
        self,
        expense_id: uuid.UUID,
        void_data: ExpenseVoidDTO,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
        idempotency_key: Optional[str] = None,
    ) -> Expense:
        """Void an active expense record (Owner only).

        Preserves immutable financial history, emits a finance trace event,
        and marks expense voided.
        """
        check_permission(actor_role, Permission.EXPENSES_VOID)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            req_hash = compute_request_hash(void_data)
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:void",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                resp = ExpenseResponseDTO.model_validate_json(payload_str)
                existing = await self._expense_repo.get_by_id(self._organization_id, resp.id)
                if existing is not None:
                    return existing

        expense = await self.get_expense(expense_id, actor_role)

        if expense.status == ExpenseStatus.VOIDED.value:
            raise ValidationException("Expense is already voided")
        if expense.status == ExpenseStatus.CORRECTED.value:
            raise ValidationException("Cannot void an expense that has already been corrected")

        now = datetime.now(timezone.utc)
        expense.status = ExpenseStatus.VOIDED.value
        expense.voided_at = now
        reason_clean = void_data.reason.strip()
        current_desc = expense.description or ""
        expense.description = f"[VOIDED: {reason_clean}] {current_desc}".strip()
        self._session.add(expense)
        await self._session.flush()

        await self._trace_service.record_event(
            action=TraceAction.FINANCE_RECORD_VOIDED,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="expense",
            target_id=expense.id,
            metadata={
                "expense_id": str(expense.id),
                "amount_minor": expense.amount_minor,
                "currency_code": expense.currency_code,
                "void_reason": reason_clean,
            },
        )
        await self._session.flush()

        if clean_key and req_hash:
            resp_dto = ExpenseResponseDTO.model_validate(expense)
            await self._idempotency_service.record_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:void",
                idempotency_key=clean_key,
                request_hash=req_hash,
                response_code=200,
                response_payload=resp_dto.model_dump_json(),
            )

        return expense

    async def correct_expense(
        self,
        expense_id: uuid.UUID,
        correction_data: ExpenseCorrectDTO,
        actor_user_id: uuid.UUID,
        actor_role: str | MemberRole,
        idempotency_key: Optional[str] = None,
    ) -> Expense:
        """Correct an active expense by issuing an auditable replacement (Owner and Manager).

        Marks original as 'corrected', links 'corrects_expense_id' and
        'replaced_by_expense_id', and emits a finance trace event.
        """
        check_permission(actor_role, Permission.EXPENSES_CORRECT)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            req_hash = compute_request_hash(correction_data)
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:correct",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                resp = ExpenseResponseDTO.model_validate_json(payload_str)
                existing = await self._expense_repo.get_by_id(self._organization_id, resp.id)
                if existing is not None:
                    return existing

        original = await self.get_expense(expense_id, actor_role)

        if original.status == ExpenseStatus.VOIDED.value:
            raise ValidationException("Cannot correct a voided expense")
        if original.status == ExpenseStatus.CORRECTED.value:
            raise ValidationException("Expense has already been corrected")

        if correction_data.amount_minor <= 0:
            raise ValidationException("Expense amount must be greater than zero")

        if correction_data.expense_category_id:
            category = await self._category_repo.get_by_id(
                self._organization_id,
                correction_data.expense_category_id,
            )
            if not category:
                raise ValidationException("Referenced expense category does not exist in this organization")

        reason_clean = correction_data.reason.strip()
        custom_desc = correction_data.description.strip() if correction_data.description else (original.description or "")
        combined_desc = f"[CORRECTION: {reason_clean}] {custom_desc}".strip()

        # Create replacement expense
        replacement = await self._expense_repo.create(
            organization_id=self._organization_id,
            amount_minor=correction_data.amount_minor,
            expense_category_id=correction_data.expense_category_id,
            occurred_at=correction_data.occurred_at or original.occurred_at,
            payment_method=correction_data.payment_method,
            payee=correction_data.payee,
            description=combined_desc,
            currency_code=correction_data.currency_code or original.currency_code,
            created_by_user_id=actor_user_id,
            corrects_expense_id=original.id,
        )

        # Update original expense
        original.status = ExpenseStatus.CORRECTED.value
        original.replaced_by_expense_id = replacement.id
        self._session.add(original)
        await self._session.flush()

        await self._trace_service.record_event(
            action=TraceAction.FINANCE_RECORD_CORRECTED,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="expense",
            target_id=original.id,
            metadata={
                "original_expense_id": str(original.id),
                "replacement_expense_id": str(replacement.id),
                "correction_reason": reason_clean,
                "original_amount_minor": original.amount_minor,
                "replacement_amount_minor": replacement.amount_minor,
            },
        )
        await self._session.flush()

        if clean_key and req_hash:
            resp_dto = ExpenseResponseDTO.model_validate(replacement)
            await self._idempotency_service.record_response(
                organization_id=self._organization_id,
                user_id=actor_user_id,
                operation="expense:correct",
                idempotency_key=clean_key,
                request_hash=req_hash,
                response_code=200,
                response_payload=resp_dto.model_dump_json(),
            )

        return replacement

"""Pydantic schemas and DTOs for expenses and expense categories (EXP-001)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.expenses.enums import (
    ExpenseCategoryStatus,
    ExpensePaymentMethod,
    ExpenseStatus,
)


class ExpenseCategoryCreateDTO(BaseModel):
    """Payload to create an expense category."""

    name: str = Field(..., min_length=1, max_length=100)


class ExpenseCategoryUpdateDTO(BaseModel):
    """Payload to update an expense category name."""

    name: str = Field(..., min_length=1, max_length=100)


class ExpenseCategoryResponseDTO(BaseModel):
    """Response DTO for an expense category."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    status: ExpenseCategoryStatus
    created_at: datetime
    updated_at: datetime


class ExpenseCategoryListResponseDTO(BaseModel):
    """Paginated list of expense categories."""

    items: list[ExpenseCategoryResponseDTO]
    total: int
    limit: int
    offset: int


class ExpenseCreateDTO(BaseModel):
    """Payload to record an operational expense."""

    amount_minor: int = Field(..., gt=0, description="Positive integer minor monetary units (e.g. Paisas)")
    expense_category_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    payment_method: ExpensePaymentMethod = ExpensePaymentMethod.CASH
    payee: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)


class ExpenseVoidDTO(BaseModel):
    """Payload to void an active expense."""

    reason: str = Field(..., min_length=3, max_length=255)


class ExpenseCorrectDTO(BaseModel):
    """Payload to correct an active expense with replacement values."""

    reason: str = Field(..., min_length=3, max_length=255)
    amount_minor: int = Field(..., gt=0)
    expense_category_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    payment_method: ExpensePaymentMethod = ExpensePaymentMethod.CASH
    payee: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)


class ExpenseResponseDTO(BaseModel):
    """Response DTO for an expense record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    expense_category_id: uuid.UUID | None = None
    amount_minor: int
    currency_code: str
    occurred_at: datetime
    payment_method: ExpensePaymentMethod
    payee: str | None = None
    description: str | None = None
    status: ExpenseStatus
    created_by_user_id: uuid.UUID | None = None
    corrects_expense_id: uuid.UUID | None = None
    replaced_by_expense_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    voided_at: datetime | None = None


class ExpenseListResponseDTO(BaseModel):
    """Paginated list of expense records."""

    items: list[ExpenseResponseDTO]
    total: int
    limit: int
    offset: int


class DailyExpenseTotalDTO(BaseModel):
    """Summary of active expense total for a single date."""

    date: str
    total_minor: int
    expense_count: int
    currency_code: str = "PKR"

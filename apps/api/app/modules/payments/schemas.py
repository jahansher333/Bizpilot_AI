"""Pydantic schemas for Payments domain (PAY-001, PAY-003, PAY-004)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.enums import PaymentChannel, PaymentStatus


class PaymentBase(BaseModel):
    """Base fields for a payment receipt."""

    amount_minor: int = Field(gt=0, description="Payment amount in integer minor units (e.g. cents/paisa)")
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)
    channel: PaymentChannel
    account_label: Optional[str] = Field(default=None, max_length=128)
    external_reference: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = Field(default=None, max_length=2000)


class PaymentCreate(PaymentBase):
    """Request schema to record a new payment receipt."""

    customer_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    received_at: Optional[datetime] = None


class PaymentVoidRequest(BaseModel):
    """Request schema to void a recorded payment."""

    reason: str = Field(min_length=1, max_length=500, description="Mandatory reason for voiding payment receipt")


class PaymentCorrectionRequest(BaseModel):
    """Request schema to correct a recorded payment."""

    amount_minor: Optional[int] = Field(default=None, gt=0, description="New amount in integer minor units")
    channel: Optional[PaymentChannel] = None
    customer_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    account_label: Optional[str] = Field(default=None, max_length=128)
    external_reference: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = Field(default=None, max_length=2000)
    reason: str = Field(min_length=1, max_length=500, description="Mandatory explanation of the correction")


class PaymentResponse(PaymentBase):
    """Response schema for a recorded payment receipt."""

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    received_at: datetime
    status: PaymentStatus
    created_by_user_id: Optional[uuid.UUID] = None
    corrects_payment_id: Optional[uuid.UUID] = None
    replaced_by_payment_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    voided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponse(BaseModel):
    """Paginated list of payments."""

    items: list[PaymentResponse]
    total: int
    limit: int
    offset: int

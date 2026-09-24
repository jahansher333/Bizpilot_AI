"""Pydantic schemas for order requests and responses (ORD-001, ORD-002)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderItemCreateSchema(BaseModel):
    """Line item input for order creation."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID = Field(..., description="ID of the catalog product being purchased")
    quantity: int = Field(..., gt=0, description="Positive integer quantity")
    unit_price_minor: int = Field(..., ge=0, description="Agreed unit price in minor currency units")


class OrderCreateSchema(BaseModel):
    """Payload to create an order."""

    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = Field(default=None, description="Optional customer ID")
    items: Sequence[OrderItemCreateSchema] = Field(..., min_length=1, description="List of items in order")
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)
    ordered_at: datetime | None = Field(default=None, description="Optional sale timestamp")

    @field_validator("currency_code")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class OrderVoidRequestSchema(BaseModel):
    """Payload to void an active order."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=255, description="Mandatory reason for voiding order")


class OrderCorrectRequestSchema(BaseModel):
    """Payload to correct an active order with replacement details."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=255, description="Mandatory reason for correcting order")
    customer_id: uuid.UUID | None = Field(default=None, description="Optional customer ID")
    items: Sequence[OrderItemCreateSchema] = Field(..., min_length=1, description="Replacement line items")
    currency_code: str = Field(default="PKR", min_length=3, max_length=3)
    ordered_at: datetime | None = Field(default=None, description="Optional sale timestamp")

    @field_validator("currency_code")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class OrderItemResponseSchema(BaseModel):

    """Order item with frozen snapshots."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID | None = None
    product_name_snapshot: str
    product_code_snapshot: str
    unit_snapshot: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int
    currency_code: str
    created_at: datetime


class OrderResponseSchema(BaseModel):
    """Order presentation schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID | None = None
    ordered_at: datetime
    status: str
    order_total_minor: int
    currency_code: str
    created_by_user_id: uuid.UUID | None = None
    corrects_order_id: uuid.UUID | None = None
    replaced_by_order_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    voided_at: datetime | None = None
    items: Sequence[OrderItemResponseSchema] = Field(default_factory=list)


class OrderListResponseSchema(BaseModel):
    """Paginated list of orders."""

    items: Sequence[OrderResponseSchema]
    total: int
    limit: int
    offset: int

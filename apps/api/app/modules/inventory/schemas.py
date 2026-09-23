"""Pydantic schemas for inventory balances and movements (INV-001, INV-002)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.inventory.enums import MovementType


class OpeningStockRequest(BaseModel):
    """Request schema for recording initial opening stock."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity: int = Field(gt=0, description="Opening stock quantity must be greater than zero")
    reason: str | None = Field(default="Opening stock", max_length=255)


class AdjustmentRequest(BaseModel):
    """Request schema for adjusting stock."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity_delta: int = Field(description="Quantity delta must be non-zero")
    reason: str = Field(min_length=3, max_length=255, description="Reason is required for manual adjustments")

    @field_validator("quantity_delta")
    @classmethod
    def validate_non_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Quantity delta must be non-zero")
        return v


class CorrectionRequest(BaseModel):
    """Request schema for correcting an inventory record."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity_delta: int = Field(description="Correction delta must be non-zero")
    reason: str = Field(min_length=3, max_length=255, description="Reason is required for corrections")

    @field_validator("quantity_delta")
    @classmethod
    def validate_non_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Quantity delta must be non-zero")
        return v


class VoidReversalRequest(BaseModel):
    """Request schema for recording a void reversal movement."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    quantity_delta: int = Field(description="Reversal delta must be non-zero")
    source_id: uuid.UUID | None = None
    reason: str | None = Field(default="Void reversal", max_length=255)

    @field_validator("quantity_delta")
    @classmethod
    def validate_non_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Quantity delta must be non-zero")
        return v


class InventoryBalanceResponse(BaseModel):
    """Schema for inventory balance response."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    on_hand_quantity: int
    version: int
    updated_at: datetime


class InventoryBalanceListResponse(BaseModel):
    """Paginated list response for inventory balances."""

    model_config = ConfigDict(extra="forbid")

    items: list[InventoryBalanceResponse]
    total: int
    limit: int
    offset: int


class InventoryMovementResponse(BaseModel):
    """Schema for inventory movement response."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    organization_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: MovementType
    quantity_delta: int
    source_type: str
    source_id: uuid.UUID | None
    reason: str | None
    created_by_user_id: uuid.UUID | None
    created_at: datetime


class InventoryMovementListResponse(BaseModel):
    """Paginated list response for inventory movements."""

    model_config = ConfigDict(extra="forbid")

    items: list[InventoryMovementResponse]
    total: int
    limit: int
    offset: int


class InventoryMutationResponse(BaseModel):
    """Response returned by mutating inventory endpoints containing balance and movement."""

    model_config = ConfigDict(extra="forbid")

    balance: InventoryBalanceResponse
    movement: InventoryMovementResponse

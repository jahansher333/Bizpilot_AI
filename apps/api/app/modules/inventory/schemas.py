"""Pydantic schemas for inventory balances and movements (INV-001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventory.enums import MovementType


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

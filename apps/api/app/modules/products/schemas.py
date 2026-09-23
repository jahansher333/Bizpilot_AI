"""Pydantic V2 schemas for product endpoints (CAT-002)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    """Request payload to create a new product."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Product code or SKU, unique within tenant while active.",
    )
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Product display name.",
    )
    category_id: Optional[uuid.UUID] = Field(
        None,
        description="Optional category ID within the same tenant.",
    )
    base_unit: str = Field(
        default="piece",
        min_length=1,
        max_length=32,
        description="Base inventory/sales unit (e.g. piece, kg, box).",
    )
    default_price_minor: int = Field(
        default=0,
        ge=0,
        description="Default selling price in minor currency units (paisas). Non-negative integer.",
    )

    @field_validator("code")
    @classmethod
    def validate_code_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("Product code must be at least 1 character")
        if len(trimmed) > 64:
            raise ValueError("Product code must be at most 64 characters")
        return trimmed

    @field_validator("name")
    @classmethod
    def validate_name_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Product name must be at least 2 characters")
        if len(trimmed) > 255:
            raise ValueError("Product name must be at most 255 characters")
        return trimmed

    @field_validator("base_unit")
    @classmethod
    def validate_base_unit_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("Base unit must be at least 1 character")
        if len(trimmed) > 32:
            raise ValueError("Base unit must be at most 32 characters")
        return trimmed


class ProductUpdate(BaseModel):
    """Request payload to update an existing product.

    All fields are optional. Omitted fields remain untouched.
    Explicitly providing `category_id=None` uncategorizes the product.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    code: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description="Updated product code/SKU.",
    )
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=255,
        description="Updated product display name.",
    )
    category_id: Optional[uuid.UUID] = Field(
        None,
        description="Updated category ID, or null to uncategorize.",
    )
    base_unit: Optional[str] = Field(
        None,
        min_length=1,
        max_length=32,
        description="Updated base unit.",
    )
    default_price_minor: Optional[int] = Field(
        None,
        ge=0,
        description="Updated default price in minor units (paisas). Non-negative integer.",
    )

    @field_validator("code")
    @classmethod
    def validate_code_trimmed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("Product code must be at least 1 character")
        if len(trimmed) > 64:
            raise ValueError("Product code must be at most 64 characters")
        return trimmed

    @field_validator("name")
    @classmethod
    def validate_name_trimmed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Product name must be at least 2 characters")
        if len(trimmed) > 255:
            raise ValueError("Product name must be at most 255 characters")
        return trimmed

    @field_validator("base_unit")
    @classmethod
    def validate_base_unit_trimmed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("Base unit must be at least 1 character")
        if len(trimmed) > 32:
            raise ValueError("Base unit must be at most 32 characters")
        return trimmed


class ProductResponse(BaseModel):
    """Safe response payload representing a product."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: uuid.UUID = Field(..., description="Product unique identifier.")
    organization_id: uuid.UUID = Field(..., description="Tenant organization unique identifier.")
    category_id: Optional[uuid.UUID] = Field(None, description="Category unique identifier if categorized.")
    code: str = Field(..., description="Product code / SKU.")
    name: str = Field(..., description="Product display name.")
    base_unit: str = Field(..., description="Base inventory unit.")
    default_price_minor: int = Field(..., description="Default price in minor currency units.")
    currency_code: str = Field(..., description="Currency code (e.g. PKR).")
    status: str = Field(..., description="Product lifecycle status (active, archived).")
    created_by_user_id: Optional[uuid.UUID] = Field(None, description="User who created the product.")
    created_at: datetime = Field(..., description="Creation timestamp in UTC.")
    updated_at: datetime = Field(..., description="Last update timestamp in UTC.")
    archived_at: Optional[datetime] = Field(None, description="Archive timestamp in UTC if archived.")


class ProductListResponse(BaseModel):
    """Paginated list response payload for products."""

    model_config = ConfigDict(extra="forbid")

    items: list[ProductResponse] = Field(..., description="List of product records.")
    total: int = Field(..., ge=0, description="Total count of products matching query.")
    limit: int = Field(..., ge=1, le=100, description="Pagination page limit applied.")
    offset: int = Field(..., ge=0, description="Pagination offset applied.")

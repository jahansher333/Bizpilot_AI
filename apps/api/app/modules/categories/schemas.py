"""Pydantic V2 schemas for category endpoints (CAT-001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreate(BaseModel):
    """Request payload to create a new category."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Category display name.",
    )

    @field_validator("name")
    @classmethod
    def validate_name_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Category name must be at least 2 characters")
        if len(trimmed) > 100:
            raise ValueError("Category name must be at most 100 characters")
        return trimmed


class CategoryUpdate(BaseModel):
    """Request payload to update an existing category."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Updated category display name.",
    )

    @field_validator("name")
    @classmethod
    def validate_name_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Category name must be at least 2 characters")
        if len(trimmed) > 100:
            raise ValueError("Category name must be at most 100 characters")
        return trimmed


class CategoryResponse(BaseModel):
    """Safe response payload representing a category."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: uuid.UUID = Field(..., description="Category unique identifier.")
    organization_id: uuid.UUID = Field(..., description="Tenant organization unique identifier.")
    name: str = Field(..., description="Category display name.")
    status: str = Field(..., description="Category lifecycle status (active, archived).")
    created_by_user_id: Optional[uuid.UUID] = Field(None, description="User who created the category.")
    created_at: datetime = Field(..., description="Creation timestamp in UTC.")
    updated_at: datetime = Field(..., description="Last update timestamp in UTC.")
    archived_at: Optional[datetime] = Field(None, description="Archive timestamp in UTC if archived.")


class CategoryListResponse(BaseModel):
    """Paginated list response payload for categories."""

    model_config = ConfigDict(extra="forbid")

    items: list[CategoryResponse] = Field(..., description="List of category records.")
    total: int = Field(..., ge=0, description="Total count of categories matching query.")
    limit: int = Field(..., ge=1, le=100, description="Pagination page limit applied.")
    offset: int = Field(..., ge=0, description="Pagination offset applied.")

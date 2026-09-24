"""Pydantic schemas for customer payloads and responses (CUS-001, CUS-002)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_phone(value: str | None) -> str | None:
    """Normalize phone string: strip whitespace, hyphens, parentheses, and unify +92/0092 to 0."""
    if value is None:
        return None
    val = value.strip()
    if not val:
        return None
    # Remove separators: spaces, hyphens, parens, dots
    cleaned = re.sub(r"[\s\-\(\)\.]", "", val)
    if not cleaned:
        return None
    # Standardize Pakistani country codes to local national prefix (03XXXXXXXXX)
    if cleaned.startswith("+92"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("0092"):
        cleaned = "0" + cleaned[4:]
    return cleaned


class CustomerCreateSchema(BaseModel):
    """Payload to create a customer."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Customer full or business name")
    phone: str | None = Field(default=None, max_length=32, description="Optional contact phone")
    email: str | None = Field(default=None, max_length=255, description="Optional contact email")
    notes: str | None = Field(default=None, max_length=2000, description="Optional notes")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Customer name cannot be empty or blank")
        return trimmed

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed if trimmed else None


class CustomerUpdateSchema(BaseModel):
    """Payload to update a customer."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Customer name cannot be empty or blank")
        return trimmed

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed if trimmed else None


class CustomerResponseSchema(BaseModel):
    """Customer presentation schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    status: str
    created_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class CustomerListResponseSchema(BaseModel):
    """Paginated list of customers."""

    items: Sequence[CustomerResponseSchema]
    total: int
    limit: int
    offset: int

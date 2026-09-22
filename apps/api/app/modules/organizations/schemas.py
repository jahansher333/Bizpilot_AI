"""Pydantic V2 schemas for organization endpoints (ORG-001)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


CURRENCY_CODE_REGEX = re.compile(r"^[A-Z]{3}$")


class CreateOrganizationRequest(BaseModel):
    """Request payload to create a new organization workspace."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    display_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Business display name.",
    )
    currency_code: str = Field(
        default="PKR",
        min_length=3,
        max_length=3,
        description="3-letter ISO 4217 currency code.",
    )
    timezone: str = Field(
        default="Asia/Karachi",
        min_length=3,
        max_length=64,
        description="Valid IANA timezone name.",
    )

    @field_validator("display_name")
    @classmethod
    def validate_display_name_trimmed(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Display name must be at least 2 characters")
        if len(trimmed) > 255:
            raise ValueError("Display name must be at most 255 characters")
        return trimmed

    @field_validator("currency_code")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        code = v.strip().upper()
        if not CURRENCY_CODE_REGEX.match(code):
            raise ValueError("Currency code must be exactly 3 uppercase ASCII letters")
        return code

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        tz_name = v.strip()
        try:
            ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError, Exception):
            raise ValueError("Invalid IANA timezone")
        return tz_name


class OrganizationResponse(BaseModel):
    """Safe response payload for organization representation."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: str = Field(..., description="Organization unique identifier.")
    display_name: str = Field(..., description="Business display name.")
    currency_code: str = Field(..., description="3-letter ISO currency code.")
    timezone: str = Field(..., description="IANA timezone name.")
    status: str = Field(..., description="Organization status.")
    created_at: datetime = Field(..., description="Creation timestamp in UTC.")
    role: str = Field(..., description="Caller's active membership role.")

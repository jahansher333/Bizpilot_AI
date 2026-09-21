"""Pydantic schemas for authentication and registration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Valid user email address",
    )
    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="Plaintext user password to be validated against policy",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User full display name",
    )

    @field_validator("display_name")
    @classmethod
    def validate_display_name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name must not be blank")
        return stripped


class RegisterResponse(BaseModel):
    """Uniform, non-enumerating registration response."""

    message: str = "Registration request accepted. Please proceed to login."


class LoginRequest(BaseModel):
    """Request payload for user authentication."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    email: EmailStr = Field(
        ...,
        max_length=255,
        description="User email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Plaintext user password",
    )


class LoginResponse(BaseModel):
    """Response payload returned upon successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserMeResponse(BaseModel):
    """Minimal trusted authenticated identity response."""

    id: str
    email: str
    display_name: str
    status: str

"""Pydantic schemas for authentication and registration."""

from __future__ import annotations

from datetime import datetime

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
    """Login service result. Internal: the router returns SessionResponse and moves the refresh
    token into the HttpOnly cookie, so it never reaches page scripts."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime | None = None


class RefreshRequest(BaseModel):
    """Request payload for access token renewal and refresh token rotation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    refresh_token: str = Field(
        ...,
        min_length=32,
        max_length=128,
        description="Opaque cryptographically random refresh token",
    )


class RefreshResponse(BaseModel):
    """Refresh service result. Internal, like LoginResponse."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime | None = None


class SessionResponse(BaseModel):
    """Public body of login and refresh: the short-lived access token only.

    The refresh token is delivered as the HttpOnly bizpilot_refresh cookie (SEC-P1 F3).
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int



class LogoutRequest(BaseModel):
    """Request payload for current session logout."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    refresh_token: str = Field(
        ...,
        min_length=32,
        max_length=128,
        description="Opaque refresh token identifying the session family to terminate.",
    )


class LogoutResponse(BaseModel):
    """Response payload for successful session termination."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="success", description="Status string.")
    message: str = Field(default="Logged out successfully", description="User-facing summary message.")


class ForgotPasswordRequest(BaseModel):
    """Request payload to initiate password recovery."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Registered user email address.",
    )


class ForgotPasswordResponse(BaseModel):
    """Uniform non-enumerating response for password recovery requests."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="success", description="Status string.")
    message: str = Field(
        default="If an eligible account exists for this email, password recovery instructions have been sent.",
        description="User-facing summary message.",
    )


class ResetPasswordRequest(BaseModel):
    """Request payload to complete password reset."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    token: str = Field(
        ...,
        min_length=32,
        max_length=128,
        description="Opaque single-use password reset token.",
    )
    new_password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="New account password meeting policy requirements.",
    )


class ResetPasswordResponse(BaseModel):
    """Response payload for successful password reset."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="success", description="Status string.")
    message: str = Field(
        default="Password reset successfully. Please log in with your new password.",
        description="User-facing summary message.",
    )


class UserMeResponse(BaseModel):
    """Minimal trusted authenticated identity response."""

    id: str
    email: str
    display_name: str
    status: str

"""Unit tests for authentication and registration schemas."""

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import RegisterRequest, RegisterResponse


def test_register_request_valid() -> None:
    """Verify valid registration input parses successfully."""
    req = RegisterRequest(
        email="test.user@example.com",
        password="ValidPassphrase123!",
        display_name="Test User",
    )
    assert req.email == "test.user@example.com"
    assert req.password == "ValidPassphrase123!"
    assert req.display_name == "Test User"


def test_register_request_trims_display_name_and_email() -> None:
    """Verify leading and trailing whitespace are trimmed."""
    req = RegisterRequest(
        email="  user@example.com  ",
        password="ValidPassphrase123!",
        display_name="  Display Name  ",
    )
    assert req.email == "user@example.com"
    assert req.display_name == "Display Name"


def test_register_request_rejects_empty_or_whitespace_display_name() -> None:
    """Verify empty or blank display name raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        RegisterRequest(
            email="user@example.com",
            password="ValidPassphrase123!",
            display_name="   ",
        )
    assert "at least 1 character" in str(exc.value) or "Display name must not be blank" in str(exc.value)

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="ValidPassphrase123!",
            display_name="",
        )


def test_register_request_rejects_malformed_email() -> None:
    """Verify invalid email formats raise ValidationError."""
    invalid_emails = [
        "not-an-email",
        "@example.com",
        "user@",
        "user@.com",
        "user@com",
        "user space@example.com",
    ]
    for bad_email in invalid_emails:
        with pytest.raises(ValidationError):
            RegisterRequest(
                email=bad_email,
                password="ValidPassphrase123!",
                display_name="Valid User",
            )


def test_register_request_rejects_password_too_short() -> None:
    """Verify password shorter than 12 characters is rejected by schema."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="short",
            display_name="Valid User",
        )


def test_register_request_rejects_password_too_long() -> None:
    """Verify password longer than 128 characters is rejected by schema."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="a" * 129,
            display_name="Valid User",
        )


def test_register_request_forbids_extra_fields() -> None:
    """Verify extraneous fields (status, role, is_admin, etc.) are strictly forbidden."""
    forbidden_payloads = [
        {"status": "admin"},
        {"role": "owner"},
        {"is_admin": True},
        {"organization_id": "00000000-0000-0000-0000-000000000000"},
        {"password_hash": "precomputed_hash"},
        {"permissions": ["all"]},
    ]
    for extra in forbidden_payloads:
        payload = {
            "email": "user@example.com",
            "password": "ValidPassphrase123!",
            "display_name": "Valid User",
            **extra,
        }
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(**payload)
        assert "extra_forbidden" in str(exc.value) or "Extra inputs are not permitted" in str(exc.value)


def test_register_response_default_message() -> None:
    """Verify default message on RegisterResponse follows approved uniform contract."""
    resp = RegisterResponse()
    assert resp.message == "Registration request accepted. Please proceed to login."

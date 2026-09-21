"""Unit tests for authentication models, enums, UUID strategy, and security repr."""

import uuid

import pytest

from app.modules.auth.enums import UserStatus
from app.modules.auth.models import (
    PasswordResetToken,
    RefreshToken,
    User,
    UserCredential,
    generate_uuid,
)


def test_generate_uuid_validity() -> None:
    """Verify generate_uuid returns a valid UUID conforming to the approved strategy."""
    uid = generate_uuid()
    assert isinstance(uid, uuid.UUID)
    if hasattr(uuid, "uuid7"):
        assert uid.version == 7
    else:
        assert uid.version == 4


def test_user_status_enum_values() -> None:
    """Verify UserStatus values match approved states."""
    assert UserStatus.ACTIVE == "active"
    assert UserStatus.DISABLED == "disabled"
    assert UserStatus.PENDING == "pending"
    assert len(UserStatus) == 3


def test_user_model_defaults() -> None:
    """Verify default values on User model instantiation."""
    u = User(
        email_normalized="owner@example.com",
        display_name="Test Owner",
    )
    assert isinstance(u.id, uuid.UUID)
    assert u.status == "active"
    assert u.email_normalized == "owner@example.com"
    assert u.display_name == "Test Owner"
    assert "owner@example.com" in repr(u)


def test_user_credential_repr_masks_password_hash() -> None:
    """Verify UserCredential repr NEVER reveals the password_hash."""
    secret_hash = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQ$secretencodedhashvalue"
    cred = UserCredential(
        user_id=uuid.uuid4(),
        password_hash=secret_hash,
    )
    repr_str = repr(cred)
    assert secret_hash not in repr_str
    assert "password_hash" not in repr_str
    assert str(cred.user_id) in repr_str


def test_refresh_token_repr_masks_token_hash() -> None:
    """Verify RefreshToken repr NEVER reveals the token_hash."""
    secret_token_hash = "a" * 64
    family_id = uuid.uuid4()
    rt = RefreshToken(
        user_id=uuid.uuid4(),
        token_hash=secret_token_hash,
        token_family_id=family_id,
        expires_at=None,  # type: ignore[arg-type]
    )
    repr_str = repr(rt)
    assert secret_token_hash not in repr_str
    assert "token_hash" not in repr_str
    assert str(family_id) in repr_str


def test_password_reset_token_repr_masks_token_hash() -> None:
    """Verify PasswordResetToken repr NEVER reveals the token_hash."""
    secret_reset_hash = "b" * 64
    prt = PasswordResetToken(
        user_id=uuid.uuid4(),
        token_hash=secret_reset_hash,
        expires_at=None,  # type: ignore[arg-type]
    )
    repr_str = repr(prt)
    assert secret_reset_hash not in repr_str
    assert "token_hash" not in repr_str


def test_no_plaintext_password_column() -> None:
    """Security check: assert no plaintext password attribute exists on User or UserCredential."""
    user_columns = {c.key for c in User.__table__.columns}
    assert "password" not in user_columns
    assert "password_plain" not in user_columns

    cred_columns = {c.key for c in UserCredential.__table__.columns}
    assert "password" not in cred_columns
    assert "password_hash" in cred_columns


def test_no_raw_token_columns() -> None:
    """Security check: assert only hashed token columns exist on token tables."""
    rt_columns = {c.key for c in RefreshToken.__table__.columns}
    assert "token" not in rt_columns
    assert "token_raw" not in rt_columns
    assert "token_hash" in rt_columns

    prt_columns = {c.key for c in PasswordResetToken.__table__.columns}
    assert "token" not in prt_columns
    assert "token_raw" not in prt_columns
    assert "token_hash" in prt_columns

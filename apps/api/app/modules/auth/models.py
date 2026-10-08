"""SQLAlchemy models for authentication, identity, and token persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.modules.auth.enums import UserStatus


def generate_uuid() -> uuid.UUID:
    """Generate UUIDv7 if cleanly supported by Python standard library, else fallback to UUIDv4.

    Complies with DATABASE-DESIGN.md Section 7.
    """
    if hasattr(uuid, "uuid7"):
        return uuid.uuid7()
    return uuid.uuid4()


class User(Base):
    """Core user identity entity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    email_normalized: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'pending')",
            name="status",
        ),
    )

    # Referential relationships: restrictive delete (no cascade) per Founder Decision Option A
    credential: Mapped[Optional[UserCredential]] = relationship(
        "UserCredential",
        back_populates="user",
        uselist=False,
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        "PasswordResetToken",
        back_populates="user",
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", generate_uuid())
        kwargs.setdefault("status", UserStatus.ACTIVE.value)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<User id={self.id} email_normalized={self.email_normalized!r} status={self.status!r}>"


class UserCredential(Base):
    """User credential record storing password hash."""

    __tablename__ = "user_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    password_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="credential")

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", generate_uuid())
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        # Never expose password_hash in string representation
        return f"<UserCredential id={self.id} user_id={self.user_id}>"


class RefreshToken(Base):
    """Hashed refresh token entity with token family metadata."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    token_family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Set when this token was consumed by rotation: the successor issued in its place. Lets the
    # refresh service tell a lost rotation response (client retries) from a replayed stolen token.
    replaced_by_token_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        # NO ACTION like every auth foreign key (Founder Option A: no cascading deletes).
        ForeignKey("refresh_tokens.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", generate_uuid())
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        # Never expose token_hash in string representation
        return f"<RefreshToken id={self.id} user_id={self.user_id} token_family_id={self.token_family_id} expires_at={self.expires_at}>"


class PasswordResetToken(Base):
    """Hashed single-use password reset token entity."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="password_reset_tokens")

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", generate_uuid())
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        # Never expose token_hash in string representation
        return f"<PasswordResetToken id={self.id} user_id={self.user_id} expires_at={self.expires_at} consumed_at={self.consumed_at}>"


class AuthRateLimitBucket(Base):
    """Fixed-window attempt counter for credential and recovery endpoints.

    The subject (email/IP) is stored only as a SHA-256 digest, never in raw form.
    """

    __tablename__ = "auth_rate_limit_buckets"

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
    )

    def __repr__(self) -> str:
        return f"<AuthRateLimitBucket scope={self.scope!r} attempt_count={self.attempt_count}>"

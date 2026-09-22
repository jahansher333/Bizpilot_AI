"""SQLAlchemy models for organizations and organization members (ORG-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.modules.auth.models import generate_uuid
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)


class Organization(Base):
    """Tenant boundary and business workspace entity."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="PKR",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Karachi",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrganizationStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(trim(display_name)) >= 2",
            name="ck_organizations_display_name_len",
        ),
        CheckConstraint(
            "char_length(currency_code) = 3",
            name="ck_organizations_currency_code_len",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled', 'archived')",
            name="ck_organizations_status",
        ),
    )


class OrganizationMember(Base):
    """Organization membership and role entity."""

    __tablename__ = "organization_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MemberRole.OWNER.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MemberStatus.ACTIVE.value,
    )
    invited_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="members",
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'manager', 'staff')",
            name="ck_organization_members_role",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked', 'invited')",
            name="ck_organization_members_status",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_members_org_user",
        ),
    )

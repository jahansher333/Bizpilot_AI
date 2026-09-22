"""Async database repository for organizations and memberships (ORG-001)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember


class OrganizationRepository:
    """PostgreSQL data access layer for organizations and organization members."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_organization(
        self,
        display_name: str,
        currency_code: str = "PKR",
        timezone: str = "Asia/Karachi",
        status: str = OrganizationStatus.ACTIVE.value,
    ) -> Organization:
        """Create and flush a new organization entity."""
        org = Organization(
            display_name=display_name,
            currency_code=currency_code,
            timezone=timezone,
            status=status,
        )
        self._session.add(org)
        await self._session.flush()
        return org

    async def create_member(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = MemberRole.OWNER.value,
        status: str = MemberStatus.ACTIVE.value,
        invited_by_user_id: Optional[uuid.UUID] = None,
    ) -> OrganizationMember:
        """Create and flush a new organization membership entity."""
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            status=status,
            invited_by_user_id=invited_by_user_id,
        )
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_organization_with_active_membership(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[tuple[Organization, OrganizationMember]]:
        """Fetch an organization combined with the caller's active membership.

        Guarantees that access is strictly scoped to active members.
        """
        stmt = (
            select(Organization, OrganizationMember)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                Organization.id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.ACTIVE.value,
                Organization.status == OrganizationStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def list_user_organizations_with_active_memberships(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[tuple[Organization, OrganizationMember]]:
        """List all organizations where the specified user has an active membership."""
        stmt = (
            select(Organization, OrganizationMember)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.ACTIVE.value,
            )
            .order_by(Organization.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetch user by normalized email."""
        stmt = select(User).where(User.email_normalized == email.strip().lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_member(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[OrganizationMember]:
        """Fetch organization member by organization and user ID."""
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_member_by_id(
        self,
        organization_id: uuid.UUID,
        member_id: uuid.UUID,
    ) -> Optional[tuple[OrganizationMember, User]]:
        """Fetch organization member by ID strictly scoped to organization, joined with user."""
        stmt = (
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.id == member_id,
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def list_members(
        self,
        organization_id: uuid.UUID,
    ) -> Sequence[tuple[OrganizationMember, User]]:
        """List all members of an organization joined with user identity."""
        stmt = (
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def count_active_owners(
        self,
        organization_id: uuid.UUID,
        for_update: bool = False,
    ) -> int:
        """Count active owners of an organization with optional row-level locking."""
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == MemberRole.OWNER.value,
            OrganizationMember.status == MemberStatus.ACTIVE.value,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def get_pending_invitation(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[tuple[OrganizationMember, User]]:
        """Fetch pending invitation for user in organization."""
        stmt = (
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.INVITED.value,
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

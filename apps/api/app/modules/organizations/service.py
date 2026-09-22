"""Domain service orchestrating organization and membership operations (ORG-001)."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationException, NotFoundException
from app.modules.auth.enums import UserStatus
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationResponse,
)


class OrganizationService:
    """Domain service managing organization workspace lifecycle and initial membership."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[OrganizationRepository] = None,
    ) -> None:
        self._session = session
        self._repository = repository or OrganizationRepository(session)

    async def create_organization(
        self,
        current_user: AuthenticatedUser,
        request: CreateOrganizationRequest,
    ) -> OrganizationResponse:
        """Atomically create a new organization and founding owner membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        # Atomic persistence: organization + owner membership in single transaction
        org = await self._repository.create_organization(
            display_name=request.display_name,
            currency_code=request.currency_code,
            timezone=request.timezone,
            status=OrganizationStatus.ACTIVE.value,
        )

        member = await self._repository.create_member(
            organization_id=org.id,
            user_id=current_user.id,
            role=MemberRole.OWNER.value,
            status=MemberStatus.ACTIVE.value,
            invited_by_user_id=None,
        )

        return OrganizationResponse(
            id=str(org.id),
            display_name=org.display_name,
            currency_code=org.currency_code,
            timezone=org.timezone,
            status=org.status,
            created_at=org.created_at,
            role=member.role,
        )

    async def get_organization(
        self,
        current_user: AuthenticatedUser,
        organization_id: uuid.UUID,
    ) -> OrganizationResponse:
        """Retrieve organization details strictly scoped to caller's active membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        row = await self._repository.get_organization_with_active_membership(
            organization_id=organization_id,
            user_id=current_user.id,
        )
        if row is None:
            raise NotFoundException("Organization not found")

        org, member = row
        return OrganizationResponse(
            id=str(org.id),
            display_name=org.display_name,
            currency_code=org.currency_code,
            timezone=org.timezone,
            status=org.status,
            created_at=org.created_at,
            role=member.role,
        )

    async def list_organizations(
        self,
        current_user: AuthenticatedUser,
    ) -> list[OrganizationResponse]:
        """List all organizations where caller has an active membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        rows = await self._repository.list_user_organizations_with_active_memberships(
            user_id=current_user.id
        )
        return [
            OrganizationResponse(
                id=str(org.id),
                display_name=org.display_name,
                currency_code=org.currency_code,
                timezone=org.timezone,
                status=org.status,
                created_at=org.created_at,
                role=member.role,
            )
            for org, member in rows
        ]

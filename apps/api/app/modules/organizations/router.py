"""FastAPI router for organization workspace endpoints (ORG-001)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.tokens import AuthenticatedUser, get_current_user
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    InviteMemberRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    UpdateMemberRoleRequest,
)
from app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization workspace",
    description="Atomically creates a new business organization workspace and establishes caller as founding Owner.",
)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationResponse:
    """Create a new organization and assign caller as owner."""
    service = OrganizationService(session)
    return await service.create_organization(current_user, request)


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organization by ID",
    description="Retrieves organization workspace details strictly scoped to caller's active membership.",
)
async def get_organization(
    organization_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationResponse:
    """Get organization by ID, scoped to active membership."""
    service = OrganizationService(session)
    return await service.get_organization(current_user, organization_id)


@router.get(
    "",
    response_model=list[OrganizationResponse],
    status_code=status.HTTP_200_OK,
    summary="List caller's organizations",
    description="Lists all organization workspaces where caller holds an active membership.",
)
async def list_organizations(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrganizationResponse]:
    """List all organizations where caller is an active member."""
    service = OrganizationService(session)
    return await service.list_organizations(current_user)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite team member",
    description="Invites an existing registered user to the organization with a specified role. Restricted to active Owners.",
)
async def invite_member(
    organization_id: uuid.UUID,
    request: InviteMemberRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMemberResponse:
    """Invite a registered user to join the organization."""
    service = OrganizationService(session)
    return await service.invite_member(organization_id, current_user, request)


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List organization members",
    description="Lists all members of the organization. Restricted to active Owners.",
)
async def list_members(
    organization_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrganizationMemberResponse]:
    """List all members of an organization."""
    service = OrganizationService(session)
    return await service.list_members(organization_id, current_user)


@router.post(
    "/{organization_id}/members/accept",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept organization invitation",
    description="Accepts a pending invitation to join an organization.",
)
async def accept_invitation(
    organization_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMemberResponse:
    """Accept a pending invitation to an organization."""
    service = OrganizationService(session)
    return await service.accept_invitation(organization_id, current_user)


@router.patch(
    "/{organization_id}/members/{member_id}",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update member role",
    description="Updates an organization member's role with last-owner protection. Restricted to active Owners.",
)
async def update_member_role(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    request: UpdateMemberRoleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMemberResponse:
    """Update an organization member's role."""
    service = OrganizationService(session)
    return await service.update_member_role(organization_id, member_id, current_user, request)


@router.delete(
    "/{organization_id}/members/{member_id}",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke member",
    description="Revokes an organization member's access with last-owner protection. Restricted to active Owners.",
)
async def revoke_member(
    organization_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationMemberResponse:
    """Revoke an organization member's access."""
    service = OrganizationService(session)
    return await service.revoke_member(organization_id, member_id, current_user)

"""FastAPI router for organization workspace endpoints (ORG-001)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.tokens import AuthenticatedUser, get_current_user
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationResponse,
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

"""FastAPI router for tenant-scoped category endpoints (CAT-001)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.modules.categories.service import CategoryService
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

router = APIRouter(
    prefix="/organizations/{organization_id}/categories",
    tags=["categories"],
)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    description="Creates a new active category within the organization. Requires categories:create permission.",
)
async def create_category(
    organization_id: uuid.UUID,
    request: CategoryCreate,
    context: RequestContext = Depends(require_permission(Permission.CATEGORIES_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> CategoryResponse:
    """Create a new category in the organization."""
    service = CategoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
    )
    return await service.create_category(request)


@router.get(
    "",
    response_model=CategoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List categories",
    description="Lists categories in the organization with pagination and optional status filter. Requires categories:read permission.",
)
async def list_categories(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Optional status filter: 'active' or 'archived'"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.CATEGORIES_READ)),
    session: AsyncSession = Depends(get_session),
) -> CategoryListResponse:
    """List categories in the organization."""
    service = CategoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
    )
    return await service.list_categories(status=status, limit=limit, offset=offset)


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category",
    description="Retrieves a single category by ID within the organization. Requires categories:read permission.",
)
async def get_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.CATEGORIES_READ)),
    session: AsyncSession = Depends(get_session),
) -> CategoryResponse:
    """Get category by ID within the organization."""
    service = CategoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
    )
    return await service.get_category(category_id)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update category",
    description="Updates a category's name within the organization. Requires categories:update permission.",
)
async def update_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    request: CategoryUpdate,
    context: RequestContext = Depends(require_permission(Permission.CATEGORIES_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> CategoryResponse:
    """Update category within the organization."""
    service = CategoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
    )
    return await service.update_category(category_id, request)


@router.post(
    "/{category_id}/archive",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive category",
    description="Archives a category within the organization. Requires categories:archive permission.",
)
async def archive_category(
    organization_id: uuid.UUID,
    category_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.CATEGORIES_ARCHIVE)),
    session: AsyncSession = Depends(get_session),
) -> CategoryResponse:
    """Archive category within the organization."""
    service = CategoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
    )
    return await service.archive_category(category_id)

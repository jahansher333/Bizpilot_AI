"""FastAPI router for tenant-scoped product endpoints (CAT-002)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.products.service import ProductService

router = APIRouter(
    prefix="/organizations/{organization_id}/products",
    tags=["products"],
)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    description="Creates a new active product within the organization. Requires products:create permission.",
)
async def create_product(
    organization_id: uuid.UUID,
    request: ProductCreate,
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> ProductResponse:
    """Create a new product in the organization."""
    service = ProductService(
        session=session,
        organization_id=context.organization_id,
        currency_code=context.organization.currency_code,
        actor_user_id=context.user_id,
    )
    return await service.create_product(request)


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List products",
    description="Lists products in the organization with pagination and optional filters. Requires products:read permission.",
)
async def list_products(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Optional status filter: 'active' or 'archived'"),
    category_id: Optional[uuid.UUID] = Query(None, description="Optional category filter"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_READ)),
    session: AsyncSession = Depends(get_session),
) -> ProductListResponse:
    """List products in the organization."""
    service = ProductService(
        session=session,
        organization_id=context.organization_id,
        currency_code=context.organization.currency_code,
        actor_user_id=context.user_id,
    )
    return await service.list_products(
        status=status,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product",
    description="Retrieves a single product by ID within the organization. Requires products:read permission.",
)
async def get_product(
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_READ)),
    session: AsyncSession = Depends(get_session),
) -> ProductResponse:
    """Get product by ID within the organization."""
    service = ProductService(
        session=session,
        organization_id=context.organization_id,
        currency_code=context.organization.currency_code,
        actor_user_id=context.user_id,
    )
    return await service.get_product(product_id)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product",
    description="Updates a product within the organization. Requires products:update permission.",
)
async def update_product(
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
    request: ProductUpdate,
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> ProductResponse:
    """Update product within the organization."""
    service = ProductService(
        session=session,
        organization_id=context.organization_id,
        currency_code=context.organization.currency_code,
        actor_user_id=context.user_id,
    )
    return await service.update_product(product_id, request)


@router.post(
    "/{product_id}/archive",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive product",
    description="Archives a product within the organization. Requires products:archive permission.",
)
async def archive_product(
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_ARCHIVE)),
    session: AsyncSession = Depends(get_session),
) -> ProductResponse:
    """Archive product within the organization."""
    service = ProductService(
        session=session,
        organization_id=context.organization_id,
        currency_code=context.organization.currency_code,
        actor_user_id=context.user_id,
    )
    return await service.archive_product(product_id)

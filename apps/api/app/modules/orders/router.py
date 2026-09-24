"""FastAPI router for tenant-scoped orders endpoints (ORD-006)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.orders.schemas import (
    OrderCorrectRequestSchema,
    OrderCreateSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
    OrderVoidRequestSchema,
)
from app.modules.orders.service import OrderService
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

router = APIRouter(
    prefix="/organizations/{organization_id}/orders",
    tags=["orders"],
)


@router.post(
    "",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create order",
    description="Creates a new active order, atomically deducting inventory stock. Requires orders:create permission.",
)
async def create_order(
    organization_id: uuid.UUID,
    request: OrderCreateSchema,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.ORDERS_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> OrderResponseSchema:
    """Create a new order within the organization."""
    service = OrderService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    order = await service.create_order(request, idempotency_key=idempotency_key)
    await session.commit()
    return order


@router.get(
    "",
    response_model=OrderListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List orders",
    description="Lists orders with pagination and optional filters. Requires orders:read permission.",
)
async def list_orders(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Optional status filter: 'active', 'voided', 'corrected'"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Optional customer ID filter"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.ORDERS_READ)),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponseSchema:
    """List orders for the organization."""
    service = OrderService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    return await service.list_orders(
        status=status,
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get order",
    description="Retrieves a single order by ID with line item snapshots. Requires orders:read permission.",
)
async def get_order(
    organization_id: uuid.UUID,
    order_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.ORDERS_READ)),
    session: AsyncSession = Depends(get_session),
) -> OrderResponseSchema:
    """Get single order by ID."""
    service = OrderService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    return await service.get_order(order_id)


@router.post(
    "/{order_id}/void",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Void order",
    description="Voids an active order and restores inventory stock. Owner-only. Requires orders:void permission.",
)
async def void_order(
    organization_id: uuid.UUID,
    order_id: uuid.UUID,
    request: OrderVoidRequestSchema,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.ORDERS_VOID)),
    session: AsyncSession = Depends(get_session),
) -> OrderResponseSchema:
    """Void order (Owner-only operation)."""
    service = OrderService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    order = await service.void_order(order_id, request, idempotency_key=idempotency_key)
    await session.commit()
    return order


@router.post(
    "/{order_id}/correct",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Correct order",
    description="Corrects an active order by creating a linked replacement order. Requires orders:correct permission.",
)
async def correct_order(
    organization_id: uuid.UUID,
    order_id: uuid.UUID,
    request: OrderCorrectRequestSchema,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.ORDERS_CORRECT)),
    session: AsyncSession = Depends(get_session),
) -> OrderResponseSchema:
    """Correct order by creating a replacement order."""
    service = OrderService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    replacement = await service.correct_order(order_id, request, idempotency_key=idempotency_key)
    await session.commit()
    return replacement

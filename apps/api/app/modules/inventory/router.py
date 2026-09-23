"""FastAPI router for tenant-scoped inventory endpoints (INV-004)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException
from app.db.session import get_session
from app.modules.idempotency.service import IdempotencyService, compute_request_hash
from app.modules.inventory.schemas import (
    AdjustmentRequest,
    CorrectionRequest,
    InventoryBalanceListResponse,
    InventoryBalanceResponse,
    InventoryMovementListResponse,
    InventoryMutationResponse,
    OpeningStockRequest,
    VoidReversalRequest,
)
from app.modules.inventory.service import InventoryService
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

router = APIRouter(
    prefix="/organizations/{organization_id}/inventory",
    tags=["inventory"],
)


@router.get(
    "/balances",
    response_model=InventoryBalanceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List inventory balances",
    description="Lists inventory balances with pagination. Requires inventory:read permission.",
)
async def list_balances(
    organization_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_READ)),
    session: AsyncSession = Depends(get_session),
) -> InventoryBalanceListResponse:
    """List inventory balances for the bound organization."""
    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    return await service.list_balances(limit=limit, offset=offset)


@router.get(
    "/balances/{product_id}",
    response_model=InventoryBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory balance for product",
    description="Retrieves the current stock balance for a single product. Requires inventory:read permission.",
)
async def get_balance(
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_READ)),
    session: AsyncSession = Depends(get_session),
) -> InventoryBalanceResponse:
    """Get current inventory balance for product."""
    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    balance = await service.get_balance(product_id)
    if balance is None:
        raise NotFoundException(f"Inventory balance for product {product_id} not found")
    return balance


@router.get(
    "/movements",
    response_model=InventoryMovementListResponse,
    status_code=status.HTTP_200_OK,
    summary="List inventory movements",
    description="Lists append-only inventory movements with optional filtering. Requires inventory:read permission.",
)
async def list_movements(
    organization_id: uuid.UUID,
    product_id: Optional[uuid.UUID] = Query(None, description="Optional product filter"),
    movement_type: Optional[str] = Query(None, description="Optional movement type filter"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_READ)),
    session: AsyncSession = Depends(get_session),
) -> InventoryMovementListResponse:
    """List inventory movements for the bound organization."""
    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    return await service.list_movements(
        product_id=product_id,
        movement_type=movement_type,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/opening-stock",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record opening stock",
    description="Records initial opening stock for a product. Allowed at most once. Requires inventory:adjust permission.",
)
async def record_opening_stock(
    organization_id: uuid.UUID,
    request: OpeningStockRequest,
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_ADJUST)),
    session: AsyncSession = Depends(get_session),
) -> InventoryMutationResponse:
    """Record initial opening stock."""
    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    bal, mov = await service.record_opening_stock(request)
    await session.commit()
    return InventoryMutationResponse(balance=bal, movement=mov)


@router.post(
    "/adjustments",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Record stock adjustment",
    description="Records a manual inventory adjustment with mandatory reason and optional idempotency. Requires inventory:adjust permission.",
)
async def record_adjustment(
    organization_id: uuid.UUID,
    request: AdjustmentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_ADJUST)),
    session: AsyncSession = Depends(get_session),
) -> InventoryMutationResponse:
    """Record stock adjustment with idempotency support."""
    idempotency_service = IdempotencyService(session)
    clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

    if clean_key:
        req_hash = compute_request_hash(request)
        cached = await idempotency_service.get_stored_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_adjustment",
            idempotency_key=clean_key,
            request_hash=req_hash,
        )
        if cached:
            _, payload_str = cached
            return InventoryMutationResponse.model_validate_json(payload_str)

    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    bal, mov = await service.record_adjustment(request)
    response = InventoryMutationResponse(balance=bal, movement=mov)

    if clean_key:
        await idempotency_service.record_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_adjustment",
            idempotency_key=clean_key,
            request_hash=req_hash,
            response_code=200,
            response_payload=response.model_dump_json(),
        )

    await session.commit()
    return response


@router.post(
    "/corrections",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Record count correction",
    description="Records an inventory count correction with mandatory reason and optional idempotency. Requires inventory:adjust permission.",
)
async def record_correction(
    organization_id: uuid.UUID,
    request: CorrectionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_ADJUST)),
    session: AsyncSession = Depends(get_session),
) -> InventoryMutationResponse:
    """Record count correction with idempotency support."""
    idempotency_service = IdempotencyService(session)
    clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

    if clean_key:
        req_hash = compute_request_hash(request)
        cached = await idempotency_service.get_stored_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_correction",
            idempotency_key=clean_key,
            request_hash=req_hash,
        )
        if cached:
            _, payload_str = cached
            return InventoryMutationResponse.model_validate_json(payload_str)

    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    bal, mov = await service.record_correction(request)
    response = InventoryMutationResponse(balance=bal, movement=mov)

    if clean_key:
        await idempotency_service.record_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_correction",
            idempotency_key=clean_key,
            request_hash=req_hash,
            response_code=200,
            response_payload=response.model_dump_json(),
        )

    await session.commit()
    return response


@router.post(
    "/void-reversals",
    response_model=InventoryMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Record void reversal",
    description="Records a void reversal movement. Strictly authorized to Organization Owner.",
)
async def record_void_reversal(
    organization_id: uuid.UUID,
    request: VoidReversalRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.INVENTORY_ADJUST)),
    session: AsyncSession = Depends(get_session),
) -> InventoryMutationResponse:
    """Record void reversal (strictly Owner authorized)."""
    idempotency_service = IdempotencyService(session)
    clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None

    if clean_key:
        req_hash = compute_request_hash(request)
        cached = await idempotency_service.get_stored_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_void_reversal",
            idempotency_key=clean_key,
            request_hash=req_hash,
        )
        if cached:
            _, payload_str = cached
            return InventoryMutationResponse.model_validate_json(payload_str)

    service = InventoryService(
        session=session,
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    bal, mov = await service.record_void_reversal(request)
    response = InventoryMutationResponse(balance=bal, movement=mov)

    if clean_key:
        await idempotency_service.record_response(
            organization_id=context.organization_id,
            user_id=context.user_id,
            operation="inventory_void_reversal",
            idempotency_key=clean_key,
            request_hash=req_hash,
            response_code=200,
            response_payload=response.model_dump_json(),
        )

    await session.commit()
    return response

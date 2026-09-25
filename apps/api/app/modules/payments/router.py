"""FastAPI router for tenant-scoped payment endpoints (PAY-004)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission
from app.modules.payments.schemas import (
    PaymentCorrectionRequest,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentVoidRequest,
)
from app.modules.payments.service import PaymentService

router = APIRouter(
    prefix="/organizations/{organization_id}/payments",
    tags=["payments"],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record payment",
    description="Records a business payment receipt. Supports retry-safe idempotency via Idempotency-Key. Requires payments:create permission.",
)
async def record_payment(
    organization_id: uuid.UUID,
    request: PaymentCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission(Permission.PAYMENTS_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> PaymentResponse:
    """Record a business payment receipt."""
    service = PaymentService(
        session=session,
        organization_id=context.organization_id,
    )
    payment = await service.record_payment(
        payment_in=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return payment


@router.get(
    "",
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List payments",
    description="Lists payments with pagination and optional filters. Requires payments:read permission.",
)
async def list_payments(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Optional status filter: 'active', 'voided', 'corrected'"),
    channel: Optional[str] = Query(None, description="Optional channel filter: 'cash', 'bank_transfer', 'digital', 'other'"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Optional customer ID filter"),
    order_id: Optional[uuid.UUID] = Query(None, description="Optional order ID filter"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset (>= 0)"),
    context: RequestContext = Depends(require_permission(Permission.PAYMENTS_READ)),
    session: AsyncSession = Depends(get_session),
) -> PaymentListResponse:
    """List payments for the organization."""
    service = PaymentService(
        session=session,
        organization_id=context.organization_id,
    )
    items, total = await service.list_payments(
        actor_role=context.role,
        customer_id=customer_id,
        order_id=order_id,
        status=status,
        channel=channel,
        limit=limit,
        offset=offset,
    )
    return PaymentListResponse(
        items=[PaymentResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment",
    description="Retrieves a single payment receipt by ID. Requires payments:read permission.",
)
async def get_payment(
    organization_id: uuid.UUID,
    payment_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.PAYMENTS_READ)),
    session: AsyncSession = Depends(get_session),
) -> PaymentResponse:
    """Get single payment by ID."""
    service = PaymentService(
        session=session,
        organization_id=context.organization_id,
    )
    payment = await service.get_payment(payment_id, context.role)
    return PaymentResponse.model_validate(payment)


@router.post(
    "/{payment_id}/void",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Void payment",
    description="Voids an active payment receipt with mandatory reason. Owner-only operation. Requires payments:void permission.",
)
async def void_payment(
    organization_id: uuid.UUID,
    payment_id: uuid.UUID,
    request: PaymentVoidRequest,
    context: RequestContext = Depends(require_permission(Permission.PAYMENTS_VOID)),
    session: AsyncSession = Depends(get_session),
) -> PaymentResponse:
    """Void payment (Owner-only operation)."""
    service = PaymentService(
        session=session,
        organization_id=context.organization_id,
    )
    payment = await service.void_payment(
        payment_id=payment_id,
        void_data=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    await session.commit()
    return PaymentResponse.model_validate(payment)


@router.post(
    "/{payment_id}/correct",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Correct payment",
    description="Corrects a payment by creating a replacement and linking the original as corrected. Requires payments:correct permission.",
)
async def correct_payment(
    organization_id: uuid.UUID,
    payment_id: uuid.UUID,
    request: PaymentCorrectionRequest,
    context: RequestContext = Depends(require_permission(Permission.PAYMENTS_CORRECT)),
    session: AsyncSession = Depends(get_session),
) -> PaymentResponse:
    """Correct payment (Owner and Manager permitted)."""
    service = PaymentService(
        session=session,
        organization_id=context.organization_id,
    )
    replacement = await service.correct_payment(
        payment_id=payment_id,
        correction_data=request,
        actor_user_id=context.user_id,
        actor_role=context.role,
    )
    await session.commit()
    return PaymentResponse.model_validate(replacement)

"""FastAPI router for tenant-scoped customer endpoints (CUS-002)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.customers.balances import get_customer_balances
from app.modules.customers.schemas import (
    CustomerBalancesResponseSchema,
    CustomerCreateSchema,
    CustomerListResponseSchema,
    CustomerResponseSchema,
    CustomerUpdateSchema,
)
from app.modules.customers.service import CustomerService
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

router = APIRouter(
    prefix="/organizations/{organization_id}/customers",
    tags=["customers"],
)


@router.post(
    "",
    response_model=CustomerResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
    description="Creates a new customer within the organization. Requires customers:create permission.",
)
async def create_customer(
    organization_id: uuid.UUID,
    payload: CustomerCreateSchema,
    context: RequestContext = Depends(require_permission(Permission.CUSTOMERS_CREATE)),
    session: AsyncSession = Depends(get_session),
) -> CustomerResponseSchema:
    """Create a new customer."""
    service = CustomerService(session=session, organization_id=context.organization_id)
    customer = await service.create_customer(payload, user_id=context.user_id)
    return CustomerResponseSchema.model_validate(customer)


@router.get(
    "",
    response_model=CustomerListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List customers",
    description="Lists customers within the organization with pagination and search. Requires customers:read permission.",
)
async def list_customers(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None, description="Optional status filter: 'active' or 'archived'"),
    search: Optional[str] = Query(None, description="Optional search by name or phone"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (max 100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    context: RequestContext = Depends(require_permission(Permission.CUSTOMERS_READ)),
    session: AsyncSession = Depends(get_session),
) -> CustomerListResponseSchema:
    """List customers with search and pagination."""
    service = CustomerService(session=session, organization_id=context.organization_id)
    items, total = await service.list_customers(
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return CustomerListResponseSchema(
        items=[CustomerResponseSchema.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# Declared before "/{customer_id}" so the literal path is not parsed as a customer ID.
@router.get(
    "/balances",
    response_model=CustomerBalancesResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Customer balances",
    description=(
        "Recorded order and payment totals per customer (active records only). "
        "Financial view: Owners and Managers (dashboard:read_operational)."
    ),
)
async def customer_balances(
    organization_id: uuid.UUID,
    customer_id: Optional[uuid.UUID] = Query(None, description="Optional single customer"),
    context: RequestContext = Depends(require_permission(Permission.DASHBOARD_READ_OPERATIONAL)),
    session: AsyncSession = Depends(get_session),
) -> CustomerBalancesResponseSchema:
    """Per-customer balances plus organization totals."""
    if customer_id is not None:
        # 404 for unknown or other-tenant customers, never an empty success.
        await CustomerService(session=session, organization_id=context.organization_id).get_customer(customer_id)
    return await get_customer_balances(session, context.organization_id, customer_id)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get customer",
    description="Retrieves a specific customer within the organization. Requires customers:read permission.",
)
async def get_customer(
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.CUSTOMERS_READ)),
    session: AsyncSession = Depends(get_session),
) -> CustomerResponseSchema:
    """Retrieve customer by ID."""
    service = CustomerService(session=session, organization_id=context.organization_id)
    customer = await service.get_customer(customer_id)
    return CustomerResponseSchema.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update customer",
    description="Updates a customer's details. Requires customers:update permission.",
)
async def update_customer(
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    payload: CustomerUpdateSchema,
    context: RequestContext = Depends(require_permission(Permission.CUSTOMERS_UPDATE)),
    session: AsyncSession = Depends(get_session),
) -> CustomerResponseSchema:
    """Update customer details."""
    service = CustomerService(session=session, organization_id=context.organization_id)
    customer = await service.update_customer(customer_id, payload)
    return CustomerResponseSchema.model_validate(customer)


@router.post(
    "/{customer_id}/archive",
    response_model=CustomerResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Archive customer",
    description="Archives a customer. Requires customers:archive permission.",
)
async def archive_customer(
    organization_id: uuid.UUID,
    customer_id: uuid.UUID,
    context: RequestContext = Depends(require_permission(Permission.CUSTOMERS_ARCHIVE)),
    session: AsyncSession = Depends(get_session),
) -> CustomerResponseSchema:
    """Archive a customer."""
    service = CustomerService(session=session, organization_id=context.organization_id)
    customer = await service.archive_customer(customer_id)
    return CustomerResponseSchema.model_validate(customer)

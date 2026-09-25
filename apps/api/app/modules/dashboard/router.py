"""FastAPI router for deterministic dashboard metrics (DASH-002)."""

from __future__ import annotations

import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.dashboard.schemas import DashboardSummaryDTO
from app.modules.dashboard.service import DashboardQueryService
from app.modules.dashboard.timezone import DashboardPeriod
from app.modules.organizations.context import RequestContext, require_permission
from app.modules.organizations.permissions import Permission

dashboard_router = APIRouter(
    prefix="/organizations/{organization_id}/dashboard",
    tags=["dashboard"],
)


@dashboard_router.get(
    "",
    response_model=DashboardSummaryDTO,
    status_code=status.HTTP_200_OK,
    summary="Get operational dashboard metrics",
    description=(
        "Retrieves deterministic operational metrics including sales orders, recorded payments, "
        "low-stock inventory indicators, recent activity, and role-filtered operating expenses. "
        "Staff receives limited view with expenses omitted. Manager/Owner receives full operational summary."
    ),
)
async def get_dashboard(
    organization_id: uuid.UUID,
    period: DashboardPeriod = Query(
        default=DashboardPeriod.TODAY,
        description="Logical period for aggregations: today, yesterday, this_week, this_month, custom",
    ),
    start_date: date | None = Query(
        default=None,
        description="Custom start date (inclusive, YYYY-MM-DD), required if period=custom",
    ),
    end_date: date | None = Query(
        default=None,
        description="Custom end date (inclusive, YYYY-MM-DD), required if period=custom",
    ),
    low_stock_threshold: int = Query(
        default=10,
        ge=0,
        le=1000,
        description="Stock count threshold below which a product is considered low stock",
    ),
    context: RequestContext = Depends(require_permission(Permission.DASHBOARD_READ_LIMITED)),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummaryDTO:
    """Fetch role-aware, deterministic dashboard summary."""
    return await DashboardQueryService.get_dashboard_summary(
        session=session,
        organization_id=context.organization_id,
        caller_role=context.role,
        period=period,
        start_date=start_date,
        end_date=end_date,
        low_stock_threshold=low_stock_threshold,
    )

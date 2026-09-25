"""Integration tests for Dashboard API endpoint and role contracts (DASH-002)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.enums import MemberRole


@pytest.fixture
async def api_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with get_session overridden to db_session."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    assert reg.status_code == 202

    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login.status_code == 200
    return email, login.json()["access_token"]


async def _create_org(client: AsyncClient, token: str, name: str = "Dashboard API Org") -> str:
    res = await client.post(
        "/api/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": name, "currency_code": "PKR"},
    )
    assert res.status_code == 201
    return res.json()["id"]


async def _invite_and_accept(
    client: AsyncClient,
    owner_token: str,
    org_id: str,
    invitee_email: str,
    invitee_token: str,
    role: MemberRole,
) -> None:
    invite_res = await client.post(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": invitee_email, "role": role.value},
    )
    assert invite_res.status_code == 201

    accept_res = await client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
    )
    assert accept_res.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_api_owner_and_manager_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that Owner and Manager receive full operational dashboard summary."""
    _, owner_token = await _create_user(api_client, "dash_owner")
    mgr_email, mgr_token = await _create_user(api_client, "dash_mgr")

    org_id = await _create_org(api_client, owner_token, "Owner Mgr Org")
    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)

    # 1. Owner calls dashboard
    res_owner = await api_client.get(
        f"/api/organizations/{org_id}/dashboard",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_owner.status_code == 200
    data_owner = res_owner.json()

    assert "sales" in data_owner
    assert "payments" in data_owner
    assert "expenses" in data_owner
    assert "net_cash" in data_owner
    assert "inventory" in data_owner
    assert "recent_activity" in data_owner
    assert "freshness" in data_owner
    assert data_owner["expenses"] is not None
    assert data_owner["net_cash"] is not None

    # 2. Manager calls dashboard
    res_mgr = await api_client.get(
        f"/api/organizations/{org_id}/dashboard",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert res_mgr.status_code == 200
    data_mgr = res_mgr.json()
    assert data_mgr["expenses"] is not None
    assert data_mgr["net_cash"] is not None


@pytest.mark.asyncio
async def test_dashboard_api_staff_limited_view(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that Staff role receives limited operational dashboard without expenses."""
    _, owner_token = await _create_user(api_client, "dash_staff_owner")
    staff_email, staff_token = await _create_user(api_client, "dash_staff")

    org_id = await _create_org(api_client, owner_token, "Staff View Org")
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # Record an expense as owner
    exp_res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={
            "Authorization": f"Bearer {owner_token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "amount_minor": 15000,
            "payment_method": "cash",
            "payee": "Secret Vendor",
        },
    )
    assert exp_res.status_code == 201

    # Staff queries dashboard
    res_staff = await api_client.get(
        f"/api/organizations/{org_id}/dashboard",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert res_staff.status_code == 200
    data_staff = res_staff.json()

    assert data_staff["sales"] is not None
    assert data_staff["payments"] is not None
    assert data_staff["inventory"] is not None

    # Crucial security invariants for staff:
    assert data_staff["expenses"] is None
    assert data_staff["net_cash"] is None
    for act in data_staff["recent_activity"]:
        assert act["activity_type"] != "expense"


@pytest.mark.asyncio
async def test_dashboard_api_period_and_date_filtering(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test logical periods and custom date range query parameters."""
    _, owner_token = await _create_user(api_client, "dash_periods_owner")
    org_id = await _create_org(api_client, owner_token, "Periods Org")

    # 1. Period: yesterday
    res_yest = await api_client.get(
        f"/api/organizations/{org_id}/dashboard?period=yesterday",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_yest.status_code == 200
    assert res_yest.json()["freshness"]["period"] == "yesterday"

    # 2. Period: this_week
    res_week = await api_client.get(
        f"/api/organizations/{org_id}/dashboard?period=this_week",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_week.status_code == 200
    assert res_week.json()["freshness"]["period"] == "this_week"

    # 3. Period: this_month
    res_month = await api_client.get(
        f"/api/organizations/{org_id}/dashboard?period=this_month",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_month.status_code == 200
    assert res_month.json()["freshness"]["period"] == "this_month"

    # 4. Period: custom with dates
    res_custom = await api_client.get(
        f"/api/organizations/{org_id}/dashboard?period=custom&start_date=2026-09-01&end_date=2026-09-20",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_custom.status_code == 200
    custom_data = res_custom.json()
    assert custom_data["freshness"]["period"] == "custom"
    assert custom_data["freshness"]["local_start_date"] == "2026-09-01"
    assert custom_data["freshness"]["local_end_date"] == "2026-09-20"


@pytest.mark.asyncio
async def test_dashboard_api_cross_tenant_and_unauthorized(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test authentication and cross-tenant access boundaries."""
    _, owner_a_token = await _create_user(api_client, "dash_cross_a")
    _, owner_b_token = await _create_user(api_client, "dash_cross_b")

    org_a = await _create_org(api_client, owner_a_token, "Org A")
    org_b = await _create_org(api_client, owner_b_token, "Org B")

    # 1. Unauthenticated request -> 401
    res_unauth = await api_client.get(f"/api/organizations/{org_a}/dashboard")
    assert res_unauth.status_code == 401

    # 2. Owner B requests Org A dashboard -> 403 or 404 (IDOR protection)
    res_cross = await api_client.get(
        f"/api/organizations/{org_a}/dashboard",
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    assert res_cross.status_code in (403, 404)

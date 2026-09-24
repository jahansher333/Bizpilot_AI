"""Security and RBAC integration tests for Customer API (CUS-002)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


@pytest.fixture
async def api_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
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
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    token = login_resp.json()["access_token"]
    return email, token


async def _create_org(client: AsyncClient, token: str, name: str = "Test Org") -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


async def _add_member(
    client: AsyncClient,
    owner_token: str,
    org_id: str,
    member_email: str,
    role: str,
    member_token: str,
) -> None:
    resp = await client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": member_email, "role": role},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201

    acc_resp = await client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert acc_resp.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_customer_idor_isolation(api_client: AsyncClient) -> None:
    _, token1 = await _create_user(api_client, "owner_org1")
    org1_id = await _create_org(api_client, token1, "Org 1")

    _, token2 = await _create_user(api_client, "owner_org2")
    org2_id = await _create_org(api_client, token2, "Org 2")

    # Create customer in Org 1
    create_resp = await api_client.post(
        f"/api/organizations/{org1_id}/customers",
        json={"name": "Org 1 Secret Customer", "phone": "0300-9999999"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert create_resp.status_code == 201
    cust_id = create_resp.json()["id"]

    # Org 2 user attempts to access Org 1's customer via Org 1 endpoint -> 404 (non-disclosure)
    cross_resp1 = await api_client.get(
        f"/api/organizations/{org1_id}/customers/{cust_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert cross_resp1.status_code == 404

    # Org 2 user attempts IDOR targeting Org 1's customer via Org 2's endpoint -> 404
    cross_resp2 = await api_client.get(
        f"/api/organizations/{org2_id}/customers/{cust_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert cross_resp2.status_code == 404


@pytest.mark.asyncio
async def test_customer_rbac_matrix_staff_and_manager(api_client: AsyncClient) -> None:
    _, owner_token = await _create_user(api_client, "rbac_owner")
    org_id = await _create_org(api_client, owner_token, "RBAC Org")

    # Create Manager and Staff
    mgr_email, mgr_token = await _create_user(api_client, "rbac_mgr")
    await _add_member(api_client, owner_token, org_id, mgr_email, "manager", mgr_token)

    staff_email, staff_token = await _create_user(api_client, "rbac_staff")
    await _add_member(api_client, owner_token, org_id, staff_email, "staff", staff_token)

    # 1. Staff CAN create customer
    staff_create = await api_client.post(
        f"/api/organizations/{org_id}/customers",
        json={"name": "Staff Created Customer", "phone": "0345-1234567"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_create.status_code == 201
    cust_id = staff_create.json()["id"]

    # 2. Staff CAN list and read customers
    staff_get = await api_client.get(
        f"/api/organizations/{org_id}/customers/{cust_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_get.status_code == 200

    # 3. Staff CANNOT update customer -> 403 Forbidden
    staff_update = await api_client.patch(
        f"/api/organizations/{org_id}/customers/{cust_id}",
        json={"name": "Tampered Name"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_update.status_code == 403

    # 4. Staff CANNOT archive customer -> 403 Forbidden
    staff_archive = await api_client.post(
        f"/api/organizations/{org_id}/customers/{cust_id}/archive",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_archive.status_code == 403

    # 5. Manager CAN update customer -> 200 OK
    mgr_update = await api_client.patch(
        f"/api/organizations/{org_id}/customers/{cust_id}",
        json={"name": "Manager Updated Customer"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_update.status_code == 200
    assert mgr_update.json()["name"] == "Manager Updated Customer"

    # 6. Manager CAN archive customer -> 200 OK
    mgr_archive = await api_client.post(
        f"/api/organizations/{org_id}/customers/{cust_id}/archive",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_archive.status_code == 200
    assert mgr_archive.json()["status"] == "archived"

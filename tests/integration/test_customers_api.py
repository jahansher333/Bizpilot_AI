"""Integration tests for Customer REST API endpoints (CUS-002)."""

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
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    assert reg_resp.status_code == 202

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return email, token


async def _create_org(client: AsyncClient, token: str, name: str = "Test Org") -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_customer_api_crud_lifecycle(api_client: AsyncClient) -> None:
    _, token = await _create_user(api_client, "cust_owner")
    org_id = await _create_org(api_client, token, "Customer Test Store")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Customer
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/customers",
        json={
            "name": "Zubair Khan",
            "phone": "0321-9876543",
            "email": "zubair@example.com",
            "notes": "Regular retail customer",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    cust_data = create_resp.json()
    assert cust_data["name"] == "Zubair Khan"
    assert cust_data["phone"] == "03219876543"
    assert cust_data["status"] == "active"
    cust_id = cust_data["id"]

    # 2. Get Customer by ID
    get_resp = await api_client.get(
        f"/api/organizations/{org_id}/customers/{cust_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cust_id

    # 3. Update Customer
    patch_resp = await api_client.patch(
        f"/api/organizations/{org_id}/customers/{cust_id}",
        json={"name": "Zubair Ahmed Khan", "notes": "VIP Buyer"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Zubair Ahmed Khan"
    assert patch_resp.json()["notes"] == "VIP Buyer"

    # 4. List Customers with pagination
    list_resp = await api_client.get(
        f"/api/organizations/{org_id}/customers?limit=10&offset=0",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1
    assert any(c["id"] == cust_id for c in list_resp.json()["items"])

    # 5. Search Customers by name
    search_resp = await api_client.get(
        f"/api/organizations/{org_id}/customers?search=Zubair",
        headers=headers,
    )
    assert search_resp.status_code == 200
    assert any(c["id"] == cust_id for c in search_resp.json()["items"])

    # 6. Search Customers by phone
    search_phone_resp = await api_client.get(
        f"/api/organizations/{org_id}/customers?search=03219876543",
        headers=headers,
    )
    assert search_phone_resp.status_code == 200
    assert any(c["id"] == cust_id for c in search_phone_resp.json()["items"])

    # 7. Archive Customer
    arch_resp = await api_client.post(
        f"/api/organizations/{org_id}/customers/{cust_id}/archive",
        headers=headers,
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "archived"
    assert arch_resp.json()["archived_at"] is not None

    # 8. Re-use phone of archived customer (FD-CUS001-01)
    reuse_resp = await api_client.post(
        f"/api/organizations/{org_id}/customers",
        json={"name": "Another Person", "phone": "0321-9876543"},
        headers=headers,
    )
    assert reuse_resp.status_code == 201
    assert reuse_resp.json()["id"] != cust_id


@pytest.mark.asyncio
async def test_customer_api_uniqueness_and_cross_org(api_client: AsyncClient) -> None:
    _, token = await _create_user(api_client, "owner_phone")
    org1_id = await _create_org(api_client, token, "Store 1")
    org2_id = await _create_org(api_client, token, "Store 2")
    headers = {"Authorization": f"Bearer {token}"}

    # Create customer in Store 1
    c1_resp = await api_client.post(
        f"/api/organizations/{org1_id}/customers",
        json={"name": "Customer 1", "phone": "+92 333 1234567"},
        headers=headers,
    )
    assert c1_resp.status_code == 201

    # Conflict in same org 1 with duplicate phone
    conflict_resp = await api_client.post(
        f"/api/organizations/{org1_id}/customers",
        json={"name": "Duplicate Phone in Store 1", "phone": "0333-1234567"},
        headers=headers,
    )
    assert conflict_resp.status_code == 409

    # Duplicate phone in store 2 (different org) SUCCEEDS
    c2_resp = await api_client.post(
        f"/api/organizations/{org2_id}/customers",
        json={"name": "Customer in Store 2", "phone": "0333-1234567"},
        headers=headers,
    )
    assert c2_resp.status_code == 201

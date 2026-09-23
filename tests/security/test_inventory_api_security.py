"""Security tests for inventory API tenant isolation, IDOR defense, and RBAC matrix (INV-004)."""

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
async def sec_client(
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


async def _create_org(client: AsyncClient, token: str, name: str = "Sec Inv Org") -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _invite_and_join_member(
    client: AsyncClient,
    owner_token: str,
    org_id: str,
    invitee_email: str,
    role: MemberRole,
    invitee_token: str,
) -> None:
    inv_resp = await client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": role.value},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert inv_resp.status_code == 201

    acc_resp = await client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
    )
    assert acc_resp.status_code == 200


async def _create_product(client: AsyncClient, token: str, org_id: str, code: str) -> str:
    resp = await client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": code,
            "name": f"Product {code}",
            "base_unit": "piece",
            "default_price_minor": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ==============================================================================
# 1. Authentication & Unauthenticated Access Denied
# ==============================================================================


@pytest.mark.asyncio
async def test_unauthenticated_requests_denied(sec_client: AsyncClient) -> None:
    """All inventory endpoints require authentication."""
    fake_org = str(uuid.uuid4())
    fake_prod = str(uuid.uuid4())

    endpoints = [
        ("GET", f"/api/organizations/{fake_org}/inventory/balances"),
        ("GET", f"/api/organizations/{fake_org}/inventory/balances/{fake_prod}"),
        ("GET", f"/api/organizations/{fake_org}/inventory/movements"),
        ("POST", f"/api/organizations/{fake_org}/inventory/opening-stock"),
        ("POST", f"/api/organizations/{fake_org}/inventory/adjustments"),
        ("POST", f"/api/organizations/{fake_org}/inventory/corrections"),
        ("POST", f"/api/organizations/{fake_org}/inventory/void-reversals"),
    ]

    for method, url in endpoints:
        if method == "GET":
            resp = await sec_client.get(url)
        else:
            resp = await sec_client.post(url, json={})
        assert resp.status_code in (401, 403), f"{method} {url} returned {resp.status_code}"


# ==============================================================================
# 2. Tenant Isolation & IDOR Defense
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_tenant_inventory_isolation_and_idor(sec_client: AsyncClient) -> None:
    """User from Org A cannot read or mutate inventory in Org B."""
    _, token_a = await _create_user(sec_client, "owner_a")
    org_a = await _create_org(sec_client, token_a, "Org A")
    prod_a = await _create_product(sec_client, token_a, org_a, "PROD-A")

    _, token_b = await _create_user(sec_client, "owner_b")
    org_b = await _create_org(sec_client, token_b, "Org B")
    prod_b = await _create_product(sec_client, token_b, org_b, "PROD-B")

    # Set up opening stock in Org A
    await sec_client.post(
        f"/api/organizations/{org_a}/inventory/opening-stock",
        json={"product_id": prod_a, "quantity": 100},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Org B user attempts to access Org A's inventory routes -> 404 Not Found (not a member of Org A)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = await sec_client.get(
        f"/api/organizations/{org_a}/inventory/balances",
        headers=headers_b,
    )
    assert resp.status_code == 404

    resp = await sec_client.get(
        f"/api/organizations/{org_a}/inventory/balances/{prod_a}",
        headers=headers_b,
    )
    assert resp.status_code == 404

    resp = await sec_client.get(
        f"/api/organizations/{org_a}/inventory/movements",
        headers=headers_b,
    )
    assert resp.status_code == 404

    # Org B user in Org B attempts to use Org A's product_id -> 404 (IDOR prevented)
    idor_resp = await sec_client.post(
        f"/api/organizations/{org_b}/inventory/opening-stock",
        json={"product_id": prod_a, "quantity": 50},
        headers=headers_b,
    )
    assert idor_resp.status_code == 404


# ==============================================================================
# 3. RBAC Matrix Enforcement
# ==============================================================================


@pytest.mark.asyncio
async def test_inventory_rbac_matrix_staff_and_manager(sec_client: AsyncClient) -> None:
    """Verify Staff read-only vs Manager adjust vs Owner void privileges."""
    # 1. Setup Org and Users
    _, owner_token = await _create_user(sec_client, "inv_owner")
    org_id = await _create_org(sec_client, owner_token, "RBAC Org")
    prod_id = await _create_product(sec_client, owner_token, org_id, "SKU-RBAC-01")

    mgr_email, mgr_token = await _create_user(sec_client, "inv_mgr")
    await _invite_and_join_member(sec_client, owner_token, org_id, mgr_email, MemberRole.MANAGER, mgr_token)

    staff_email, staff_token = await _create_user(sec_client, "inv_staff")
    await _invite_and_join_member(sec_client, owner_token, org_id, staff_email, MemberRole.STAFF, staff_token)

    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Staff cannot record opening stock -> 403
    staff_open = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 50},
        headers=staff_headers,
    )
    assert staff_open.status_code == 403

    # 3. Manager CAN record opening stock -> 201
    mgr_open = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 50, "reason": "Manager opening"},
        headers=mgr_headers,
    )
    assert mgr_open.status_code == 201

    # 4. Staff CAN read balances and movements -> 200
    staff_bal = await sec_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers=staff_headers,
    )
    assert staff_bal.status_code == 200
    assert staff_bal.json()["on_hand_quantity"] == 50

    staff_movs = await sec_client.get(
        f"/api/organizations/{org_id}/inventory/movements",
        headers=staff_headers,
    )
    assert staff_movs.status_code == 200

    # 5. Staff CANNOT perform adjustments or corrections -> 403
    staff_adj = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json={"product_id": prod_id, "quantity_delta": 5, "reason": "Staff attempt"},
        headers=staff_headers,
    )
    assert staff_adj.status_code == 403

    staff_corr = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/corrections",
        json={"product_id": prod_id, "quantity_delta": -2, "reason": "Staff count attempt"},
        headers=staff_headers,
    )
    assert staff_corr.status_code == 403

    # 6. Manager CAN perform adjustments and corrections -> 200
    mgr_adj = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json={"product_id": prod_id, "quantity_delta": 10, "reason": "Stock arrived"},
        headers=mgr_headers,
    )
    assert mgr_adj.status_code == 200

    mgr_corr = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/corrections",
        json={"product_id": prod_id, "quantity_delta": -5, "reason": "Damaged goods"},
        headers=mgr_headers,
    )
    assert mgr_corr.status_code == 200
    corr_mov_id = mgr_corr.json()["movement"]["id"]

    # 7. Manager CANNOT perform void reversal -> 403 Forbidden!
    mgr_void = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/void-reversals",
        json={"product_id": prod_id, "quantity_delta": 5, "source_id": corr_mov_id, "reason": "Manager reversing"},
        headers=mgr_headers,
    )
    assert mgr_void.status_code == 403

    # 8. Staff CANNOT perform void reversal -> 403 Forbidden!
    staff_void = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/void-reversals",
        json={"product_id": prod_id, "quantity_delta": 5, "source_id": corr_mov_id},
        headers=staff_headers,
    )
    assert staff_void.status_code == 403

    # 9. Owner CAN perform void reversal -> 200 OK!
    owner_void = await sec_client.post(
        f"/api/organizations/{org_id}/inventory/void-reversals",
        json={"product_id": prod_id, "quantity_delta": 5, "source_id": corr_mov_id, "reason": "Owner voiding mistake"},
        headers=owner_headers,
    )
    assert owner_void.status_code == 200

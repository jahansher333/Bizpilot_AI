"""Integration tests for Orders API endpoints, RBAC, and idempotency (ORD-006)."""

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


async def _create_org(client: AsyncClient, token: str, name: str = "Orders Org") -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _invite_and_accept(
    client: AsyncClient,
    owner_token: str,
    org_id: str,
    member_email: str,
    member_token: str,
    role: MemberRole,
) -> None:
    invite_resp = await client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": member_email, "role": role.value},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert invite_resp.status_code == 201

    accept_resp = await client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accept_resp.status_code == 200


async def _create_product(client: AsyncClient, token: str, org_id: str, code: str, price: int = 5000) -> str:
    resp = await client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": code,
            "name": f"Product {code}",
            "base_unit": "piece",
            "default_price_minor": price,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _set_stock(client: AsyncClient, token: str, org_id: str, prod_id: str, qty: int = 100) -> None:
    resp = await client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": qty, "reason": "Initial stock"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


async def _create_customer(client: AsyncClient, token: str, org_id: str, phone: str = "03001234567") -> str:
    resp = await client.post(
        f"/api/organizations/{org_id}/customers",
        json={"name": "Valued Customer", "phone": phone},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_order_creation_listing_and_detail(api_client: AsyncClient) -> None:
    """Verify order creation by Staff, listing, and detail retrieval."""
    _, owner_token = await _create_user(api_client, "ord_owner1")
    staff_email, staff_token = await _create_user(api_client, "ord_staff1")
    org_id = await _create_org(api_client, owner_token, "Retail Store")

    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    prod_id = await _create_product(api_client, owner_token, org_id, "SKU-ORD-01", price=3000)
    await _set_stock(api_client, owner_token, org_id, prod_id, qty=50)
    cust_id = await _create_customer(api_client, owner_token, org_id, "03001112233")

    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Staff creates order
    create_payload = {
        "customer_id": cust_id,
        "items": [
            {"product_id": prod_id, "quantity": 5, "unit_price_minor": 3000},
        ],
    }
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/orders",
        json=create_payload,
        headers=staff_headers,
    )
    assert create_resp.status_code == 201
    order_data = create_resp.json()
    order_id = order_data["id"]
    assert order_data["order_total_minor"] == 15000
    assert order_data["status"] == "active"
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["product_id"] == prod_id
    assert order_data["items"][0]["quantity"] == 5

    # List orders
    list_resp = await api_client.get(
        f"/api/organizations/{org_id}/orders",
        headers=staff_headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["id"] == order_id

    # Get single order
    get_resp = await api_client.get(
        f"/api/organizations/{org_id}/orders/{order_id}",
        headers=staff_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == order_id


@pytest.mark.asyncio
async def test_order_creation_idempotency_behavior(api_client: AsyncClient) -> None:
    """Verify idempotency replay and payload conflict on order creation."""
    _, owner_token = await _create_user(api_client, "ord_idemp_owner")
    org_id = await _create_org(api_client, owner_token, "Idemp Org")
    prod_id = await _create_product(api_client, owner_token, org_id, "SKU-IDEMP-01", price=2000)
    await _set_stock(api_client, owner_token, org_id, prod_id, qty=20)

    headers = {"Authorization": f"Bearer {owner_token}", "Idempotency-Key": "idemp-key-orders-100"}
    payload = {
        "items": [{"product_id": prod_id, "quantity": 4, "unit_price_minor": 2000}],
    }

    # First request
    resp1 = await api_client.post(f"/api/organizations/{org_id}/orders", json=payload, headers=headers)
    assert resp1.status_code == 201
    order1 = resp1.json()

    # Replay identical request with same key
    resp2 = await api_client.post(f"/api/organizations/{org_id}/orders", json=payload, headers=headers)
    assert resp2.status_code == 201
    order2 = resp2.json()
    assert order1["id"] == order2["id"]

    # Verify inventory was decremented only once: 20 - 4 = 16
    bal_resp = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert bal_resp.status_code == 200
    assert bal_resp.json()["on_hand_quantity"] == 16

    # Different payload with same idempotency key -> 409 Conflict
    diff_payload = {
        "items": [{"product_id": prod_id, "quantity": 8, "unit_price_minor": 2000}],
    }
    resp3 = await api_client.post(f"/api/organizations/{org_id}/orders", json=diff_payload, headers=headers)
    assert resp3.status_code == 409


@pytest.mark.asyncio
async def test_order_void_rbac_and_stock_restoration(api_client: AsyncClient) -> None:
    """Verify Owner can void order, stock is restored, and non-owners are denied."""
    _, owner_token = await _create_user(api_client, "void_owner")
    mgr_email, mgr_token = await _create_user(api_client, "void_mgr")
    staff_email, staff_token = await _create_user(api_client, "void_staff")
    org_id = await _create_org(api_client, owner_token, "Void Org")

    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    prod_id = await _create_product(api_client, owner_token, org_id, "SKU-VOID-01", price=1000)
    await _set_stock(api_client, owner_token, org_id, prod_id, qty=30)

    # Create order: deducts 6 (balance -> 24)
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/orders",
        json={"items": [{"product_id": prod_id, "quantity": 6, "unit_price_minor": 1000}]},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["id"]

    # Staff attempt void -> 403 Forbidden
    staff_void = await api_client.post(
        f"/api/organizations/{org_id}/orders/{order_id}/void",
        json={"reason": "Staff attempt"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_void.status_code == 403

    # Manager attempt void -> 403 Forbidden (void is Owner-only)
    mgr_void = await api_client.post(
        f"/api/organizations/{org_id}/orders/{order_id}/void",
        json={"reason": "Manager attempt"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_void.status_code == 403

    # Owner void -> 200 OK
    owner_void = await api_client.post(
        f"/api/organizations/{org_id}/orders/{order_id}/void",
        json={"reason": "Customer cancellation"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_void.status_code == 200
    assert owner_void.json()["status"] == "voided"

    # Stock restored to 30
    bal_resp = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert bal_resp.json()["on_hand_quantity"] == 30

    # Voiding already voided order -> 409 Conflict
    revoid = await api_client.post(
        f"/api/organizations/{org_id}/orders/{order_id}/void",
        json={"reason": "Second void attempt"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert revoid.status_code == 409


@pytest.mark.asyncio
async def test_order_correction_rbac_and_replacement(api_client: AsyncClient) -> None:
    """Verify Manager/Owner can correct orders and Staff is denied."""
    _, owner_token = await _create_user(api_client, "corr_owner")
    mgr_email, mgr_token = await _create_user(api_client, "corr_mgr")
    staff_email, staff_token = await _create_user(api_client, "corr_staff")
    org_id = await _create_org(api_client, owner_token, "Correction Org")

    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    prod1_id = await _create_product(api_client, owner_token, org_id, "SKU-CORR-01", price=1000)
    prod2_id = await _create_product(api_client, owner_token, org_id, "SKU-CORR-02", price=2000)
    await _set_stock(api_client, owner_token, org_id, prod1_id, qty=20)
    await _set_stock(api_client, owner_token, org_id, prod2_id, qty=20)

    # Initial order: 5 of prod1 (balance: 15)
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/orders",
        json={"items": [{"product_id": prod1_id, "quantity": 5, "unit_price_minor": 1000}]},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert create_resp.status_code == 201
    orig_order_id = create_resp.json()["id"]

    # Staff attempt correct -> 403 Forbidden
    corr_payload = {
        "reason": "Change items",
        "items": [{"product_id": prod2_id, "quantity": 2, "unit_price_minor": 2000}],
    }
    staff_corr = await api_client.post(
        f"/api/organizations/{org_id}/orders/{orig_order_id}/correct",
        json=corr_payload,
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_corr.status_code == 403

    # Manager corrects -> 200 OK
    mgr_corr = await api_client.post(
        f"/api/organizations/{org_id}/orders/{orig_order_id}/correct",
        json=corr_payload,
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_corr.status_code == 200
    replacement = mgr_corr.json()
    assert replacement["status"] == "active"
    assert replacement["corrects_order_id"] == orig_order_id
    assert replacement["order_total_minor"] == 4000

    # Original order is marked corrected
    get_orig = await api_client.get(
        f"/api/organizations/{org_id}/orders/{orig_order_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert get_orig.json()["status"] == "corrected"
    assert get_orig.json()["replaced_by_order_id"] == replacement["id"]

    # Stock: prod1 restored to 20, prod2 deducted by 2 to 18
    bal1 = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod1_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    bal2 = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod2_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert bal1.json()["on_hand_quantity"] == 20
    assert bal2.json()["on_hand_quantity"] == 18


@pytest.mark.asyncio
async def test_order_filtering_and_pagination(api_client: AsyncClient) -> None:
    """Verify listing orders with status and pagination filters."""
    _, owner_token = await _create_user(api_client, "filter_owner")
    org_id = await _create_org(api_client, owner_token, "Filter Org")
    prod_id = await _create_product(api_client, owner_token, org_id, "SKU-FLT-01", price=500)
    await _set_stock(api_client, owner_token, org_id, prod_id, qty=100)

    headers = {"Authorization": f"Bearer {owner_token}"}

    # Create 3 orders
    order_ids = []
    for _ in range(3):
        res = await api_client.post(
            f"/api/organizations/{org_id}/orders",
            json={"items": [{"product_id": prod_id, "quantity": 1, "unit_price_minor": 500}]},
            headers=headers,
        )
        assert res.status_code == 201
        order_ids.append(res.json()["id"])

    # Void one order
    void_res = await api_client.post(
        f"/api/organizations/{org_id}/orders/{order_ids[0]}/void",
        json={"reason": "Void first order"},
        headers=headers,
    )
    assert void_res.status_code == 200

    # Filter active orders
    active_res = await api_client.get(f"/api/organizations/{org_id}/orders?status=active", headers=headers)
    assert active_res.status_code == 200
    assert active_res.json()["total"] == 2

    # Filter voided orders
    voided_res = await api_client.get(f"/api/organizations/{org_id}/orders?status=voided", headers=headers)
    assert voided_res.status_code == 200
    assert voided_res.json()["total"] == 1

    # Pagination: limit=1, offset=0
    page_res = await api_client.get(f"/api/organizations/{org_id}/orders?limit=1&offset=0", headers=headers)
    assert page_res.status_code == 200
    assert len(page_res.json()["items"]) == 1
    assert page_res.json()["total"] == 3

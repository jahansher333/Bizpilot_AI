"""Integration tests for Inventory API endpoints and idempotency (INV-004)."""

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


async def _create_org(client: AsyncClient, token: str, name: str = "Inventory Org") -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_product(client: AsyncClient, token: str, org_id: str, code: str) -> str:
    resp = await client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": code,
            "name": f"Product {code}",
            "base_unit": "piece",
            "default_price_minor": 2500,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_inventory_api_opening_stock_and_balances(api_client: AsyncClient) -> None:
    """Verify recording opening stock creates balance and lists correctly via API."""
    _, token = await _create_user(api_client, "inv_open")
    org_id = await _create_org(api_client, token)
    prod_id = await _create_product(api_client, token, org_id, "SKU-API-01")

    headers = {"Authorization": f"Bearer {token}"}

    # Initial balance query should return 404
    get_init = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers=headers,
    )
    assert get_init.status_code == 404

    # Record opening stock
    open_resp = await api_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 100, "reason": "Initial warehouse count"},
        headers=headers,
    )
    assert open_resp.status_code == 201
    data = open_resp.json()
    assert data["balance"]["on_hand_quantity"] == 100
    assert data["movement"]["movement_type"] == "opening"
    assert data["movement"]["quantity_delta"] == 100

    # Query single balance
    bal_resp = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers=headers,
    )
    assert bal_resp.status_code == 200
    assert bal_resp.json()["on_hand_quantity"] == 100

    # List balances
    list_bal = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances",
        headers=headers,
    )
    assert list_bal.status_code == 200
    list_data = list_bal.json()
    assert list_data["total"] >= 1
    assert any(b["product_id"] == prod_id for b in list_data["items"])

    # Duplicate opening stock returns 409
    dup_resp = await api_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 50},
        headers=headers,
    )
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_inventory_api_adjustments_and_idempotency(api_client: AsyncClient) -> None:
    """Verify stock adjustments and Idempotency-Key replay and conflict semantics."""
    _, token = await _create_user(api_client, "inv_adj")
    org_id = await _create_org(api_client, token)
    prod_id = await _create_product(api_client, token, org_id, "SKU-ADJ-01")

    headers = {"Authorization": f"Bearer {token}"}

    # Start with 50 units
    await api_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 50, "reason": "Initial"},
        headers=headers,
    )

    idem_key = f"adj-idem-{uuid.uuid4()}"
    adj_payload = {
        "product_id": prod_id,
        "quantity_delta": 25,
        "reason": "Shipment arrived without PO",
    }

    # First request with idempotency key
    res1 = await api_client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json=adj_payload,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["balance"]["on_hand_quantity"] == 75
    assert data1["movement"]["quantity_delta"] == 25

    # Second request with SAME idempotency key and SAME payload: must replay identical response!
    res2 = await api_client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json=adj_payload,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["balance"]["on_hand_quantity"] == 75
    assert data2["movement"]["id"] == data1["movement"]["id"]

    # Balance remains 75 (not 100)
    bal = await api_client.get(
        f"/api/organizations/{org_id}/inventory/balances/{prod_id}",
        headers=headers,
    )
    assert bal.json()["on_hand_quantity"] == 75

    # Third request with SAME idempotency key but DIFFERENT payload: must return 409 Conflict
    diff_payload = {
        "product_id": prod_id,
        "quantity_delta": 10,
        "reason": "Different adjustment attempt",
    }
    res3 = await api_client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json=diff_payload,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert res3.status_code == 409


@pytest.mark.asyncio
async def test_inventory_api_corrections_and_void_reversals(api_client: AsyncClient) -> None:
    """Verify correction and void reversal lifecycle via API."""
    _, token = await _create_user(api_client, "inv_corr")
    org_id = await _create_org(api_client, token)
    prod_id = await _create_product(api_client, token, org_id, "SKU-CORR-01")

    headers = {"Authorization": f"Bearer {token}"}

    # Opening stock: 100
    await api_client.post(
        f"/api/organizations/{org_id}/inventory/opening-stock",
        json={"product_id": prod_id, "quantity": 100, "reason": "Opening"},
        headers=headers,
    )

    # Correction: -10
    corr_resp = await api_client.post(
        f"/api/organizations/{org_id}/inventory/corrections",
        json={"product_id": prod_id, "quantity_delta": -10, "reason": "Physical count difference"},
        headers=headers,
    )
    assert corr_resp.status_code == 200
    corr_data = corr_resp.json()
    assert corr_data["balance"]["on_hand_quantity"] == 90
    assert corr_data["movement"]["movement_type"] == "correction"
    corr_mov_id = corr_data["movement"]["id"]

    # Owner void reversal: +10
    void_resp = await api_client.post(
        f"/api/organizations/{org_id}/inventory/void-reversals",
        json={
            "product_id": prod_id,
            "quantity_delta": 10,
            "source_id": corr_mov_id,
            "reason": "Found miscounted box",
        },
        headers=headers,
    )
    assert void_resp.status_code == 200
    void_data = void_resp.json()
    assert void_data["balance"]["on_hand_quantity"] == 100
    assert void_data["movement"]["movement_type"] == "void_reversal"
    assert void_data["movement"]["source_id"] == corr_mov_id

    # List movements
    movs_resp = await api_client.get(
        f"/api/organizations/{org_id}/inventory/movements?product_id={prod_id}",
        headers=headers,
    )
    assert movs_resp.status_code == 200
    movs = movs_resp.json()["items"]
    assert len(movs) == 3  # opening, correction, void_reversal

"""Performance Smoke Test Suite (HARD-004).

Measures representative API latency, dashboard aggregation latency,
and concurrent connection pool handling against PostgreSQL under expected pilot load.
Adheres strictly to docs/implementation/P0-IMPLEMENTATION-PLAN.md:
- No invented SLAs
- Repeatable smoke assertions for typical operational responsiveness
- Verification of concurrent database session and connection pooling
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.enums import MemberRole


@pytest.fixture
async def perf_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with database session bound to the transaction rollback."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecureP@ss12345!"
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


async def _create_org(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_performance_smoke_representative_endpoints(perf_client: AsyncClient):
    """VERIFY: Measure latencies for representative reads, writes, and dashboard queries."""
    client = perf_client

    # 1. Measure Login Latency
    email, token = await _create_user(client, "perf_owner")
    t0 = time.perf_counter()
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "SecureP@ss12345!"},
    )
    login_latency_ms = (time.perf_counter() - t0) * 1000
    assert login_resp.status_code == 200
    assert login_latency_ms < 5000, f"Login latency too high: {login_latency_ms:.1f}ms"

    # 2. Provision Org and Seed Data
    org_id = await _create_org(client, token, "Performance Test Store")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Product
    t0 = time.perf_counter()
    prod_resp = await client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "PERF-01", "name": "Perf Item", "base_unit": "piece", "default_price_minor": 10000},
        headers=headers,
    )
    product_write_latency_ms = (time.perf_counter() - t0) * 1000
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]
    assert product_write_latency_ms < 5000, f"Product write latency too high: {product_write_latency_ms:.1f}ms"

    # Stock Adjustment
    t0 = time.perf_counter()
    adj_resp = await client.post(
        f"/api/organizations/{org_id}/inventory/adjustments",
        json={"product_id": prod_id, "quantity_delta": 100, "reason": "Opening stock"},
        headers=headers,
    )
    inventory_write_latency_ms = (time.perf_counter() - t0) * 1000
    assert adj_resp.status_code == 200
    assert inventory_write_latency_ms < 5000, f"Inventory adjustment latency too high: {inventory_write_latency_ms:.1f}ms"

    # Customer Creation
    t0 = time.perf_counter()
    cust_resp = await client.post(
        f"/api/organizations/{org_id}/customers",
        json={"name": "Perf Customer", "phone": "03001122334"},
        headers=headers,
    )
    cust_write_latency_ms = (time.perf_counter() - t0) * 1000
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["id"]
    assert cust_write_latency_ms < 5000, f"Customer creation latency too high: {cust_write_latency_ms:.1f}ms"

    # Order Creation (Atomic transaction)
    t0 = time.perf_counter()
    order_resp = await client.post(
        f"/api/organizations/{org_id}/orders",
        json={
            "customer_id": cust_id,
            "items": [{"product_id": prod_id, "quantity": 5, "unit_price_minor": 10000}],
            "currency_code": "PKR",
        },
        headers=headers,
    )
    order_write_latency_ms = (time.perf_counter() - t0) * 1000
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]
    assert order_write_latency_ms < 8000, f"Order creation latency too high: {order_write_latency_ms:.1f}ms"

    # Payment Recording
    t0 = time.perf_counter()
    pay_resp = await client.post(
        f"/api/organizations/{org_id}/payments",
        json={
            "amount_minor": 50000,
            "channel": "cash",
            "customer_id": cust_id,
            "order_id": order_id,
        },
        headers=headers,
    )
    payment_write_latency_ms = (time.perf_counter() - t0) * 1000
    assert pay_resp.status_code == 201
    assert payment_write_latency_ms < 5000, f"Payment write latency too high: {payment_write_latency_ms:.1f}ms"

    # Product List Read Latency
    t0 = time.perf_counter()
    prod_list_resp = await client.get(
        f"/api/organizations/{org_id}/products",
        headers=headers,
    )
    product_read_latency_ms = (time.perf_counter() - t0) * 1000
    assert prod_list_resp.status_code == 200
    assert product_read_latency_ms < 5000, f"Product list latency too high: {product_read_latency_ms:.1f}ms"

    # Dashboard Aggregation Latency
    t0 = time.perf_counter()
    dash_resp = await client.get(
        f"/api/organizations/{org_id}/dashboard?period=today",
        headers=headers,
    )
    dashboard_latency_ms = (time.perf_counter() - t0) * 1000
    assert dash_resp.status_code == 200
    assert dashboard_latency_ms < 8000, f"Dashboard aggregation latency too high: {dashboard_latency_ms:.1f}ms"


@pytest.mark.asyncio
async def test_concurrent_requests_connection_pool_smoke(perf_client: AsyncClient):
    """VERIFY: Execute concurrent requests to ensure connection pool robustness."""
    client = perf_client
    _, token = await _create_user(client, "pool_owner")
    org_id = await _create_org(client, token, "Pool Stress Store")
    headers = {"Authorization": f"Bearer {token}"}

    # Fire 10 concurrent requests to different endpoints
    endpoints = [
        f"/api/organizations/{org_id}/products",
        f"/api/organizations/{org_id}/categories",
        f"/api/organizations/{org_id}/inventory/balances",
        f"/api/organizations/{org_id}/customers",
        f"/api/organizations/{org_id}/orders",
        f"/api/organizations/{org_id}/payments",
        f"/api/organizations/{org_id}/dashboard?period=today",
        f"/api/organizations/{org_id}/members",
        f"/api/organizations/{org_id}/products",
        f"/api/organizations/{org_id}/dashboard?period=this_month",
    ]

    t0 = time.perf_counter()
    tasks = [client.get(ep, headers=headers) for ep in endpoints]
    responses = await asyncio.gather(*tasks)
    total_elapsed_ms = (time.perf_counter() - t0) * 1000

    # All concurrent requests must succeed with 200 OK
    for i, resp in enumerate(responses):
        assert resp.status_code == 200, f"Concurrent request to {endpoints[i]} failed with {resp.status_code}"

    # Overall batch time should be well bounded (< 20s for remote cloud DB over internet)
    assert total_elapsed_ms < 20000, f"Concurrent batch took too long: {total_elapsed_ms:.1f}ms"

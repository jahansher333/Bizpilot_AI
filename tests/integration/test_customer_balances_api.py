"""Integration tests for GET /customers/balances (R5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.orders.models import Order
from app.modules.payments.models import Payment


@pytest.fixture
async def api_client(test_app: FastAPI, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _user(client: AsyncClient, prefix: str) -> tuple[str, dict[str, str]]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    assert (await client.post("/api/auth/register", json={"email": email, "password": pw, "display_name": prefix})).status_code == 202
    token = (await client.post("/api/auth/login", json={"email": email, "password": pw})).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


async def _org(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/api/organizations", json={"display_name": f"Org {uuid.uuid4().hex[:6]}"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _customer(client: AsyncClient, org_id: str, headers: dict[str, str], name: str) -> str:
    resp = await client.post(f"/api/organizations/{org_id}/customers", json={"name": name}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _order(org_id: str, customer_id: str, total: int, status: str) -> Order:
    return Order(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(org_id),
        customer_id=uuid.UUID(customer_id),
        order_number=f"ORD-{uuid.uuid4().hex[:6]}",
        status=status,
        ordered_at=datetime.now(timezone.utc),
        order_total_minor=total,
        currency_code="PKR",
    )


def _payment(org_id: str, customer_id: str, amount: int, status: str) -> Payment:
    return Payment(
        id=uuid.uuid4(),
        organization_id=uuid.UUID(org_id),
        customer_id=uuid.UUID(customer_id),
        amount_minor=amount,
        channel="cash",
        received_at=datetime.now(timezone.utc),
        status=status,
    )


@pytest.mark.asyncio
async def test_balances_count_only_active_records(api_client: AsyncClient, db_session: AsyncSession) -> None:
    _, owner = await _user(api_client, "bal_owner")
    org_id = await _org(api_client, owner)
    bilal = await _customer(api_client, org_id, owner, "Bilal General Store")
    usman = await _customer(api_client, org_id, owner, "Usman Kiryana")
    await _customer(api_client, org_id, owner, "No Orders Yet")

    db_session.add_all(
        [
            _order(org_id, bilal, 1_100_000, "active"),
            _order(org_id, bilal, 980_000, "active"),
            _order(org_id, bilal, 1_225_000, "corrected"),
            _order(org_id, bilal, 420_000, "voided"),
            _payment(org_id, bilal, 1_100_000, "active"),
            _payment(org_id, bilal, 500_000, "corrected"),
            _order(org_id, usman, 300_000, "active"),
            _payment(org_id, usman, 350_000, "active"),
        ]
    )
    await db_session.flush()

    resp = await api_client.get(f"/api/organizations/{org_id}/customers/balances", headers=owner)
    assert resp.status_code == 200
    body = resp.json()
    by_id = {item["customer_id"]: item for item in body["items"]}

    assert by_id[bilal]["order_count"] == 2
    assert by_id[bilal]["voided_order_count"] == 1
    assert by_id[bilal]["total_orders_minor"] == 2_080_000
    assert by_id[bilal]["payment_count"] == 1
    assert by_id[bilal]["total_payments_minor"] == 1_100_000
    assert by_id[bilal]["balance_minor"] == 980_000

    # Overpaid customers have a negative balance and are not counted as owing.
    assert by_id[usman]["balance_minor"] == -50_000
    assert body["customers_with_orders"] == 2
    assert body["customers_with_balance"] == 1
    assert body["outstanding_minor"] == 980_000
    assert body["currency_code"] == "PKR"

    single = await api_client.get(f"/api/organizations/{org_id}/customers/balances?customer_id={bilal}", headers=owner)
    assert single.status_code == 200
    assert [i["customer_id"] for i in single.json()["items"]] == [bilal]


@pytest.mark.asyncio
async def test_single_customer_without_records_returns_zeroes(api_client: AsyncClient) -> None:
    _, owner = await _user(api_client, "bal_zero")
    org_id = await _org(api_client, owner)
    cid = await _customer(api_client, org_id, owner, "Fresh Customer")
    resp = await api_client.get(f"/api/organizations/{org_id}/customers/balances?customer_id={cid}", headers=owner)
    assert resp.status_code == 200
    assert resp.json()["items"] == [
        {
            "customer_id": cid,
            "order_count": 0,
            "voided_order_count": 0,
            "total_orders_minor": 0,
            "payment_count": 0,
            "total_payments_minor": 0,
            "balance_minor": 0,
        }
    ]


@pytest.mark.asyncio
async def test_balances_are_tenant_scoped_and_hidden_from_staff(api_client: AsyncClient) -> None:
    _, owner_a = await _user(api_client, "bal_a")
    org_a = await _org(api_client, owner_a)
    _, owner_b = await _user(api_client, "bal_b")
    org_b = await _org(api_client, owner_b)
    foreign = await _customer(api_client, org_b, owner_b, "Other Tenant Customer")

    cross = await api_client.get(f"/api/organizations/{org_a}/customers/balances?customer_id={foreign}", headers=owner_a)
    assert cross.status_code == 404

    staff_email, staff = await _user(api_client, "bal_staff")
    invite = await api_client.post(f"/api/organizations/{org_a}/members", json={"email": staff_email, "role": "staff"}, headers=owner_a)
    assert invite.status_code == 201
    assert (await api_client.post(f"/api/organizations/{org_a}/members/accept", headers=staff)).status_code == 200

    denied = await api_client.get(f"/api/organizations/{org_a}/customers/balances", headers=staff)
    assert denied.status_code == 403
    # Staff can still read the customer list itself.
    assert (await api_client.get(f"/api/organizations/{org_a}/customers", headers=staff)).status_code == 200

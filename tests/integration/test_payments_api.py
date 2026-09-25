"""Integration tests for Payments API endpoints, RBAC, and idempotency (PAY-004)."""

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


async def _create_org(client: AsyncClient, token: str, name: str = "Payments Org") -> str:
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


@pytest.mark.asyncio
async def test_record_payment_api_happy_path_and_roles(api_client: AsyncClient) -> None:
    _, owner_tok = await _create_user(api_client, "pay_owner")
    mgr_email, mgr_tok = await _create_user(api_client, "pay_mgr")
    staff_email, staff_tok = await _create_user(api_client, "pay_staff")

    org_id = await _create_org(api_client, owner_tok, "Payment API Org")
    await _invite_and_accept(api_client, owner_tok, org_id, mgr_email, mgr_tok, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_tok, org_id, staff_email, staff_tok, MemberRole.STAFF)

    # 1. Staff can record payment (Permission.PAYMENTS_CREATE)
    resp_staff = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={
            "amount_minor": 15000,
            "currency_code": "PKR",
            "channel": "cash",
            "account_label": "Till 1",
            "external_reference": "STAFF-REC-1",
            "notes": "Cash sale payment",
        },
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert resp_staff.status_code == 201
    pay_data = resp_staff.json()
    assert pay_data["amount_minor"] == 15000
    assert pay_data["channel"] == "cash"
    assert pay_data["status"] == "active"

    # 2. Manager can record payment
    resp_mgr = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={
            "amount_minor": 25000,
            "channel": "bank_transfer",
            "account_label": "HBL Account",
            "external_reference": "MGR-REC-1",
        },
        headers={"Authorization": f"Bearer {mgr_tok}"},
    )
    assert resp_mgr.status_code == 201

    # 3. Owner can record payment
    resp_owner = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={
            "amount_minor": 35000,
            "channel": "digital",
            "account_label": "JazzCash",
            "external_reference": "OWNER-REC-1",
        },
        headers={"Authorization": f"Bearer {owner_tok}"},
    )
    assert resp_owner.status_code == 201


@pytest.mark.asyncio
async def test_payment_idempotency_api(api_client: AsyncClient) -> None:
    _, tok = await _create_user(api_client, "pay_idem_user")
    org_id = await _create_org(api_client, tok, "Idemp API Org")

    idemp_key = f"key-pay-{uuid.uuid4().hex}"
    payload = {
        "amount_minor": 45000,
        "channel": "cash",
        "account_label": "Main Cash",
        "external_reference": "IDEMP-EXT-01",
    }

    # 1. First request
    resp1 = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json=payload,
        headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idemp_key},
    )
    assert resp1.status_code == 201
    p1 = resp1.json()

    # 2. Second request with same idempotency key and same payload returns 201 with identical payment
    resp2 = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json=payload,
        headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idemp_key},
    )
    assert resp2.status_code == 201
    p2 = resp2.json()
    assert p2["id"] == p1["id"]

    # 3. Third request with same key but different payload returns 409 Conflict
    resp3 = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={**payload, "amount_minor": 99999},
        headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": idemp_key},
    )
    assert resp3.status_code == 409


@pytest.mark.asyncio
async def test_list_and_get_payments_api_with_isolation(api_client: AsyncClient) -> None:
    _, tok_a = await _create_user(api_client, "iso_a")
    _, tok_b = await _create_user(api_client, "iso_b")

    org_a = await _create_org(api_client, tok_a, "Org A")
    org_b = await _create_org(api_client, tok_b, "Org B")

    # Create payment in Org A
    create_resp = await api_client.post(
        f"/api/organizations/{org_a}/payments",
        json={"amount_minor": 12000, "channel": "cash"},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert create_resp.status_code == 201
    pay_a = create_resp.json()

    # 1. Org A lists payments
    list_a = await api_client.get(
        f"/api/organizations/{org_a}/payments",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert list_a.status_code == 200
    assert list_a.json()["total"] == 1

    # 2. Org B lists payments (empty)
    list_b = await api_client.get(
        f"/api/organizations/{org_b}/payments",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    # 3. Org B attempts to get Org A payment -> 404
    get_cross = await api_client.get(
        f"/api/organizations/{org_b}/payments/{pay_a['id']}",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert get_cross.status_code == 404


@pytest.mark.asyncio
async def test_void_payment_api_rbac(api_client: AsyncClient) -> None:
    _, owner_tok = await _create_user(api_client, "void_owner")
    mgr_email, mgr_tok = await _create_user(api_client, "void_mgr")
    staff_email, staff_tok = await _create_user(api_client, "void_staff")

    org_id = await _create_org(api_client, owner_tok, "Void API Org")
    await _invite_and_accept(api_client, owner_tok, org_id, mgr_email, mgr_tok, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_tok, org_id, staff_email, staff_tok, MemberRole.STAFF)

    # Record payment
    p_resp = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={"amount_minor": 18000, "channel": "cash"},
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert p_resp.status_code == 201
    payment_id = p_resp.json()["id"]

    # 1. Staff void attempt -> 403 Forbidden
    resp_staff = await api_client.post(
        f"/api/organizations/{org_id}/payments/{payment_id}/void",
        json={"reason": "Customer cancelled"},
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert resp_staff.status_code == 403

    # 2. Manager void attempt -> 403 Forbidden (Owner only)
    resp_mgr = await api_client.post(
        f"/api/organizations/{org_id}/payments/{payment_id}/void",
        json={"reason": "Customer cancelled"},
        headers={"Authorization": f"Bearer {mgr_tok}"},
    )
    assert resp_mgr.status_code == 403

    # 3. Owner void attempt -> 200 OK
    resp_owner = await api_client.post(
        f"/api/organizations/{org_id}/payments/{payment_id}/void",
        json={"reason": "Payment recorded in error, customer refunded"},
        headers={"Authorization": f"Bearer {owner_tok}"},
    )
    assert resp_owner.status_code == 200
    voided = resp_owner.json()
    assert voided["status"] == "voided"
    assert voided["voided_at"] is not None


@pytest.mark.asyncio
async def test_correct_payment_api_rbac(api_client: AsyncClient) -> None:
    _, owner_tok = await _create_user(api_client, "corr_owner")
    mgr_email, mgr_tok = await _create_user(api_client, "corr_mgr")
    staff_email, staff_tok = await _create_user(api_client, "corr_staff")

    org_id = await _create_org(api_client, owner_tok, "Correct API Org")
    await _invite_and_accept(api_client, owner_tok, org_id, mgr_email, mgr_tok, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_tok, org_id, staff_email, staff_tok, MemberRole.STAFF)

    # Record payment
    p_resp = await api_client.post(
        f"/api/organizations/{org_id}/payments",
        json={"amount_minor": 20000, "channel": "cash"},
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert p_resp.status_code == 201
    payment_id = p_resp.json()["id"]

    # 1. Staff correct attempt -> 403 Forbidden
    resp_staff = await api_client.post(
        f"/api/organizations/{org_id}/payments/{payment_id}/correct",
        json={"amount_minor": 22000, "reason": "Staff correction attempt"},
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert resp_staff.status_code == 403

    # 2. Manager correct attempt -> 200 OK
    resp_mgr = await api_client.post(
        f"/api/organizations/{org_id}/payments/{payment_id}/correct",
        json={
            "amount_minor": 22000,
            "channel": "bank_transfer",
            "account_label": "Meezan Bank",
            "reason": "Corrected cash to bank transfer and amount to 22000",
        },
        headers={"Authorization": f"Bearer {mgr_tok}"},
    )
    assert resp_mgr.status_code == 200
    replacement = resp_mgr.json()
    assert replacement["amount_minor"] == 22000
    assert replacement["channel"] == "bank_transfer"
    assert replacement["corrects_payment_id"] == payment_id
    assert replacement["status"] == "active"

"""Integration tests for Expenses and Expense Categories API endpoints, RBAC, and idempotency (EXP-003)."""

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


async def _create_org(client: AsyncClient, token: str, name: str = "Expenses Org") -> str:
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
async def test_expense_categories_api_rbac(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test creating, listing, updating, and archiving expense categories with RBAC."""
    _, owner_token = await _create_user(api_client, "exp_cat_owner")
    mgr_email, mgr_token = await _create_user(api_client, "exp_cat_mgr")
    staff_email, staff_token = await _create_user(api_client, "exp_cat_staff")

    org_id = await _create_org(api_client, owner_token, "Cat RBAC Org")
    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # 1. Staff cannot create categories (403)
    res_staff = await api_client.post(
        f"/api/organizations/{org_id}/expense-categories",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"name": "Office Snacks"},
    )
    assert res_staff.status_code == 403

    # 2. Manager can create category (201)
    res_mgr = await api_client.post(
        f"/api/organizations/{org_id}/expense-categories",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"name": "Office Snacks"},
    )
    assert res_mgr.status_code == 201
    cat_id = res_mgr.json()["id"]
    assert res_mgr.json()["name"] == "Office Snacks"

    # 3. Manager can update category name (200)
    res_upd = await api_client.put(
        f"/api/organizations/{org_id}/expense-categories/{cat_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"name": "Pantry & Snacks"},
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "Pantry & Snacks"

    # 4. Staff cannot list categories (403)
    res_list_staff = await api_client.get(
        f"/api/organizations/{org_id}/expense-categories",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert res_list_staff.status_code == 403

    # 5. Owner can list categories (200)
    res_list_owner = await api_client.get(
        f"/api/organizations/{org_id}/expense-categories",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_list_owner.status_code == 200
    assert len(res_list_owner.json()["items"]) == 1

    # 6. Archive category (200)
    res_arch = await api_client.post(
        f"/api/organizations/{org_id}/expense-categories/{cat_id}/archive",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert res_arch.status_code == 200
    assert res_arch.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_record_expense_api_and_idempotency(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test recording expenses via API, RBAC checks, and Idempotency-Key support."""
    _, owner_token = await _create_user(api_client, "exp_rec_owner")
    mgr_email, mgr_token = await _create_user(api_client, "exp_rec_mgr")
    staff_email, staff_token = await _create_user(api_client, "exp_rec_staff")

    org_id = await _create_org(api_client, owner_token, "Expense Record Org")
    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # 1. Staff cannot record expenses (403)
    staff_res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"amount_minor": 10000, "payment_method": "cash"},
    )
    assert staff_res.status_code == 403

    # 2. Manager records expense with Idempotency-Key
    idem_key = f"idem-api-exp-{uuid.uuid4().hex}"
    payload = {
        "amount_minor": 45000,
        "payment_method": "cash",
        "payee": "Local Hardware",
        "description": "Store repairs",
    }
    mgr_res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={
            "Authorization": f"Bearer {mgr_token}",
            "Idempotency-Key": idem_key,
        },
        json=payload,
    )
    assert mgr_res.status_code == 201
    exp_id = mgr_res.json()["id"]
    assert mgr_res.json()["amount_minor"] == 45000
    await db_session.commit()

    # 3. Retry with same Idempotency-Key: safe replay
    replay_res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={
            "Authorization": f"Bearer {mgr_token}",
            "Idempotency-Key": idem_key,
        },
        json=payload,
    )
    assert replay_res.status_code == 201
    assert replay_res.json()["id"] == exp_id

    # 4. Retry with same key but changed amount: 409 Conflict
    conflict_payload = {**payload, "amount_minor": 55000}
    conflict_res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={
            "Authorization": f"Bearer {mgr_token}",
            "Idempotency-Key": idem_key,
        },
        json=conflict_payload,
    )
    assert conflict_res.status_code == 409


@pytest.mark.asyncio
async def test_void_expense_api_rbac(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test voiding expense API: Owner allowed, Manager and Staff denied."""
    _, owner_token = await _create_user(api_client, "exp_void_owner")
    mgr_email, mgr_token = await _create_user(api_client, "exp_void_mgr")
    staff_email, staff_token = await _create_user(api_client, "exp_void_staff")

    org_id = await _create_org(api_client, owner_token, "Expense Void Org")
    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # Record active expense
    res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"amount_minor": 20000, "payment_method": "cash"},
    )
    assert res.status_code == 201
    expense_id = res.json()["id"]
    await db_session.commit()

    # 1. Staff void attempt: 403
    staff_void = await api_client.post(
        f"/api/organizations/{org_id}/expenses/{expense_id}/void",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"reason": "Mistake by staff"},
    )
    assert staff_void.status_code == 403

    # 2. Manager void attempt: 403
    mgr_void = await api_client.post(
        f"/api/organizations/{org_id}/expenses/{expense_id}/void",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"reason": "Mistake by manager"},
    )
    assert mgr_void.status_code == 403

    # 3. Owner void attempt: 200 OK
    owner_void = await api_client.post(
        f"/api/organizations/{org_id}/expenses/{expense_id}/void",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"reason": "Voucher cancelled by owner"},
    )
    assert owner_void.status_code == 200
    assert owner_void.json()["status"] == "voided"


@pytest.mark.asyncio
async def test_correct_expense_api_rbac(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test correcting expense API: Owner and Manager allowed, Staff denied."""
    _, owner_token = await _create_user(api_client, "exp_corr_owner")
    mgr_email, mgr_token = await _create_user(api_client, "exp_corr_mgr")
    staff_email, staff_token = await _create_user(api_client, "exp_corr_staff")

    org_id = await _create_org(api_client, owner_token, "Expense Correct Org")
    await _invite_and_accept(api_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)
    await _invite_and_accept(api_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # Record active expense
    res = await api_client.post(
        f"/api/organizations/{org_id}/expenses",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"amount_minor": 20000, "payment_method": "cash"},
    )
    assert res.status_code == 201
    expense_id = res.json()["id"]
    await db_session.commit()

    # 1. Staff correct attempt: 403
    staff_corr = await api_client.post(
        f"/api/organizations/{org_id}/expenses/{expense_id}/correct",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"reason": "Change amount", "amount_minor": 25000, "payment_method": "cash"},
    )
    assert staff_corr.status_code == 403

    # 2. Manager correct attempt: 200 OK
    mgr_corr = await api_client.post(
        f"/api/organizations/{org_id}/expenses/{expense_id}/correct",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"reason": "Change amount to 25000", "amount_minor": 25000, "payment_method": "cash"},
    )
    assert mgr_corr.status_code == 200
    replacement = mgr_corr.json()
    assert replacement["id"] != expense_id
    assert replacement["amount_minor"] == 25000
    assert replacement["corrects_expense_id"] == expense_id


@pytest.mark.asyncio
async def test_list_and_daily_totals_api_with_isolation(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test listing expenses, daily total endpoint, and cross-tenant non-disclosure (404)."""
    _, owner_a_token = await _create_user(api_client, "iso_owner_a")
    _, owner_b_token = await _create_user(api_client, "iso_owner_b")

    org_a = await _create_org(api_client, owner_a_token, "Org A Expenses")
    org_b = await _create_org(api_client, owner_b_token, "Org B Expenses")

    # Record expense in Org A
    res_a = await api_client.post(
        f"/api/organizations/{org_a}/expenses",
        headers={"Authorization": f"Bearer {owner_a_token}"},
        json={"amount_minor": 75000, "payment_method": "cash"},
    )
    assert res_a.status_code == 201
    expense_a_id = res_a.json()["id"]
    await db_session.commit()

    # 1. Owner B accessing Org A expense directly via Org B prefix: 404 (IDOR non-disclosure)
    res_cross = await api_client.get(
        f"/api/organizations/{org_b}/expenses/{expense_a_id}",
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    assert res_cross.status_code == 404

    # 2. Daily total in Org A reflects 75000
    res_total = await api_client.get(
        f"/api/organizations/{org_a}/expenses/daily-total",
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert res_total.status_code == 200
    assert res_total.json()["total_minor"] == 75000
    assert res_total.json()["expense_count"] == 1

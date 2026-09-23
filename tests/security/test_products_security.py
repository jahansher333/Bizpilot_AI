"""Security tests for product tenant isolation, IDOR defense, and RBAC matrix (CAT-002)."""

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
    """Register and login a user, returning email and access_token."""
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


async def _create_org(client: AsyncClient, token: str, name: str = "Sec Org") -> str:
    """Create an organization and return its ID string."""
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
    """Invite a user to an org with a specific role and accept the invitation."""
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


# ==============================================================================
# 1. Tenant Isolation & IDOR Defense
# ==============================================================================


@pytest.mark.asyncio
async def test_product_cross_tenant_isolation_and_idor(sec_client: AsyncClient) -> None:
    """Cross-tenant access attempts return 404 or 403; never leak foreign data."""
    _, token_a = await _create_user(sec_client, "owner_a")
    _, token_b = await _create_user(sec_client, "owner_b")

    org_a = await _create_org(sec_client, token_a, "Org Alpha")
    org_b = await _create_org(sec_client, token_b, "Org Beta")

    # Org A creates a product
    create_resp = await sec_client.post(
        f"/api/organizations/{org_a}/products",
        json={"code": "SECRET-A", "name": "Secret Product A", "default_price_minor": 9900},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_resp.status_code == 201
    prod_a_id = create_resp.json()["id"]

    # 1. User B tries to access Org A path -> 404 Not Found (not a member of Org A)
    cross_path_resp = await sec_client.get(
        f"/api/organizations/{org_a}/products/{prod_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_path_resp.status_code == 404

    # 2. User B tries to read Product A using Org B path -> 404 Not Found
    idor_get = await sec_client.get(
        f"/api/organizations/{org_b}/products/{prod_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_get.status_code == 404

    # 3. User B tries to update Product A using Org B path -> 404 Not Found
    idor_patch = await sec_client.patch(
        f"/api/organizations/{org_b}/products/{prod_a_id}",
        json={"name": "Hijacked Name"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_patch.status_code == 404

    # 4. User B tries to archive Product A using Org B path -> 404 Not Found
    idor_arch = await sec_client.post(
        f"/api/organizations/{org_b}/products/{prod_a_id}/archive",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_arch.status_code == 404

    # Verify Product A in Org A is completely untouched
    verify_resp = await sec_client.get(
        f"/api/organizations/{org_a}/products/{prod_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["name"] == "Secret Product A"
    assert verify_resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_product_cross_tenant_category_injection(sec_client: AsyncClient) -> None:
    """Cannot assign a category belonging to another tenant (FD-CAT002-03 -> 404)."""
    _, token_a = await _create_user(sec_client, "cat_inj_a")
    _, token_b = await _create_user(sec_client, "cat_inj_b")

    org_a = await _create_org(sec_client, token_a, "Org A")
    org_b = await _create_org(sec_client, token_b, "Org B")

    # Create category in Org A
    cat_resp = await sec_client.post(
        f"/api/organizations/{org_a}/categories",
        json={"name": "Org A Category"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert cat_resp.status_code == 201
    cat_a_id = cat_resp.json()["id"]

    # Org B tries to create product referencing Org A category -> 404
    inj_create = await sec_client.post(
        f"/api/organizations/{org_b}/products",
        json={"code": "INJ-1", "name": "Injection Test", "category_id": cat_a_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert inj_create.status_code == 404

    # Org B creates legitimate uncategorized product
    valid_create = await sec_client.post(
        f"/api/organizations/{org_b}/products",
        json={"code": "INJ-2", "name": "Valid Prod"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert valid_create.status_code == 201
    prod_b_id = valid_create.json()["id"]

    # Org B tries to update product referencing Org A category -> 404
    inj_patch = await sec_client.patch(
        f"/api/organizations/{org_b}/products/{prod_b_id}",
        json={"category_id": cat_a_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert inj_patch.status_code == 404


# ==============================================================================
# 2. RBAC Matrix Enforcement
# ==============================================================================


@pytest.mark.asyncio
async def test_product_rbac_matrix_owner_manager_staff(sec_client: AsyncClient) -> None:
    """Validate permissions: Owner=full, Manager=full catalog, Staff=read-only."""
    owner_email, owner_token = await _create_user(sec_client, "rbac_owner")
    mgr_email, mgr_token = await _create_user(sec_client, "rbac_mgr")
    staff_email, staff_token = await _create_user(sec_client, "rbac_staff")

    org_id = await _create_org(sec_client, owner_token, "RBAC Catalog Org")

    await _invite_and_join_member(
        sec_client,
        owner_token,
        org_id,
        mgr_email,
        MemberRole.MANAGER,
        mgr_token,
    )
    await _invite_and_join_member(
        sec_client,
        owner_token,
        org_id,
        staff_email,
        MemberRole.STAFF,
        staff_token,
    )

    # 1. Staff cannot create product -> 403 Forbidden
    staff_create = await sec_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "STAFF-P", "name": "Staff Item"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_create.status_code == 403

    # 2. Manager can create product -> 201
    mgr_create = await sec_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "MGR-P", "name": "Manager Item"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_create.status_code == 201
    prod_id = mgr_create.json()["id"]

    # 3. Staff can read products list and detail -> 200 OK
    staff_list = await sec_client.get(
        f"/api/organizations/{org_id}/products",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_list.status_code == 200

    staff_get = await sec_client.get(
        f"/api/organizations/{org_id}/products/{prod_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_get.status_code == 200
    assert staff_get.json()["id"] == prod_id

    # 4. Staff cannot update product -> 403 Forbidden
    staff_upd = await sec_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"name": "Hacked Name"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_upd.status_code == 403

    # 5. Staff cannot archive product -> 403 Forbidden
    staff_arch = await sec_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_arch.status_code == 403

    # 6. Manager can update product -> 200 OK
    mgr_upd = await sec_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"name": "Manager Updated Name"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_upd.status_code == 200
    assert mgr_upd.json()["name"] == "Manager Updated Name"

    # 7. Owner can archive product -> 200 OK
    owner_arch = await sec_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_arch.status_code == 200
    assert owner_arch.json()["status"] == "archived"


# ==============================================================================
# 3. Mass Assignment & Unauthenticated Rejection
# ==============================================================================


@pytest.mark.asyncio
async def test_product_mass_assignment_protection(sec_client: AsyncClient) -> None:
    """Extra fields such as organization_id, status, currency_code are forbidden (422)."""
    _, token = await _create_user(sec_client, "mass_assign")
    org_id = await _create_org(sec_client, token, "Mass Assign Org")

    # In POST
    resp1 = await sec_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "MASS-1",
            "name": "Item",
            "organization_id": str(uuid.uuid4()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 422

    resp2 = await sec_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "MASS-2", "name": "Item", "status": "archived"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 422

    # In PATCH
    prod_resp = await sec_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "MASS-3", "name": "Item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    resp3 = await sec_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"status": "archived"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_product_unauthenticated_requests_rejected(sec_client: AsyncClient) -> None:
    """Endpoints require valid authentication (401)."""
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    assert (await sec_client.post(f"/api/organizations/{org_id}/products", json={})).status_code == 401
    assert (await sec_client.get(f"/api/organizations/{org_id}/products")).status_code == 401
    assert (await sec_client.get(f"/api/organizations/{org_id}/products/{prod_id}")).status_code == 401
    assert (await sec_client.patch(f"/api/organizations/{org_id}/products/{prod_id}", json={})).status_code == 401
    assert (await sec_client.post(f"/api/organizations/{org_id}/products/{prod_id}/archive")).status_code == 401

"""End-to-End Catalog Integration and Security Tests (CAT-004).

Consolidates the complete Catalog boundary (CAT-001, CAT-002, CAT-003)
verifying cross-entity relationships, cross-tenant isolation, role-based access control,
natural idempotent archiving, and lifecycle invariants before Inventory tasks begin.
"""

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
async def cat_client(
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


async def _create_org(client: AsyncClient, token: str, name: str = "Catalog Org") -> str:
    """Create an organization and return its ID string."""
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
    """Helper for owner to invite a member and member to accept invitation."""
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
async def test_catalog_e2e_lifecycle_and_category_relationships(cat_client: AsyncClient) -> None:
    """Verify end-to-end catalog lifecycle: creation, assignment, archiving, and code reuse."""
    _, owner_token = await _create_user(cat_client, "cat_owner")
    org_id = await _create_org(cat_client, owner_token, "Acme Groceries")
    auth_header = {"Authorization": f"Bearer {owner_token}"}

    # 1. Create an active category
    cat_resp = await cat_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Beverages"},
        headers=auth_header,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    # 2. Create a product assigned to Beverages
    prod_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "TEA-001",
            "name": "Karak Chai 500g",
            "base_unit": "box",
            "default_price_minor": 45000,
            "category_id": cat_id,
        },
        headers=auth_header,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]
    assert prod_resp.json()["category_id"] == cat_id
    assert prod_resp.json()["status"] == "active"

    # 3. Archive the category
    arc_cat_resp = await cat_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=auth_header,
    )
    assert arc_cat_resp.status_code == 200
    assert arc_cat_resp.json()["status"] == "archived"
    assert arc_cat_resp.json()["archived_at"] is not None

    # Natural idempotent archiving of category
    re_arc_cat_resp = await cat_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=auth_header,
    )
    assert re_arc_cat_resp.status_code == 200
    assert re_arc_cat_resp.json()["archived_at"] == arc_cat_resp.json()["archived_at"]

    # 4. Existing product still references the archived category
    get_prod_resp = await cat_client.get(
        f"/api/organizations/{org_id}/products/{prod_id}",
        headers=auth_header,
    )
    assert get_prod_resp.status_code == 200
    assert get_prod_resp.json()["category_id"] == cat_id

    # 5. Creating a new product referencing the archived category must fail (409 Conflict)
    fail_prod_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "COFFEE-001",
            "name": "Instant Coffee",
            "base_unit": "jar",
            "default_price_minor": 85000,
            "category_id": cat_id,
        },
        headers=auth_header,
    )
    assert fail_prod_resp.status_code == 409
    assert "archived" in fail_prod_resp.json()["error"]["message"].lower()

    # 6. Updating existing product to uncategorize succeeds
    upd_resp = await cat_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"category_id": None},
        headers=auth_header,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["category_id"] is None

    # 7. Attempting to re-assign product to archived category fails (409 Conflict)
    re_assign_resp = await cat_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"category_id": cat_id},
        headers=auth_header,
    )
    assert re_assign_resp.status_code == 409

    # 8. Archive the product
    arc_prod_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers=auth_header,
    )
    assert arc_prod_resp.status_code == 200
    assert arc_prod_resp.json()["status"] == "archived"
    assert arc_prod_resp.json()["archived_at"] is not None

    # Natural idempotent archiving of product
    re_arc_prod_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers=auth_header,
    )
    assert re_arc_prod_resp.status_code == 200
    assert re_arc_prod_resp.json()["archived_at"] == arc_prod_resp.json()["archived_at"]

    # 9. Archived code reuse: A new active product can now use code TEA-001
    reuse_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "tea-001",  # case-insensitive check
            "name": "New Blend Tea 500g",
            "base_unit": "box",
            "default_price_minor": 50000,
        },
        headers=auth_header,
    )
    assert reuse_resp.status_code == 201
    assert reuse_resp.json()["code"] == "tea-001"
    assert reuse_resp.json()["status"] == "active"

    # Conflicting with active product code fails
    conflict_resp = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "TEA-001",
            "name": "Another Tea",
            "base_unit": "box",
            "default_price_minor": 55000,
        },
        headers=auth_header,
    )
    assert conflict_resp.status_code == 409


@pytest.mark.asyncio
async def test_catalog_cross_tenant_isolation_and_idor(cat_client: AsyncClient) -> None:
    """Verify complete cross-tenant boundary and IDOR defenses across categories and products."""
    _, owner_a_token = await _create_user(cat_client, "owner_a")
    org_a = await _create_org(cat_client, owner_a_token, "Tenant Alpha")
    auth_a = {"Authorization": f"Bearer {owner_a_token}"}

    _, owner_b_token = await _create_user(cat_client, "owner_b")
    org_b = await _create_org(cat_client, owner_b_token, "Tenant Beta")
    auth_b = {"Authorization": f"Bearer {owner_b_token}"}

    # Org A creates category and product
    cat_a_resp = await cat_client.post(
        f"/api/organizations/{org_a}/categories",
        json={"name": "Hardware"},
        headers=auth_a,
    )
    assert cat_a_resp.status_code == 201
    cat_a_id = cat_a_resp.json()["id"]

    prod_a_resp = await cat_client.post(
        f"/api/organizations/{org_a}/products",
        json={
            "code": "HAMMER-01",
            "name": "Steel Hammer 500g",
            "base_unit": "piece",
            "default_price_minor": 120000,
            "category_id": cat_a_id,
        },
        headers=auth_a,
    )
    assert prod_a_resp.status_code == 201
    prod_a_id = prod_a_resp.json()["id"]

    # Org B attempts to read Org A's category via Org A URL path (404 Not Found - non-member)
    resp = await cat_client.get(
        f"/api/organizations/{org_a}/categories/{cat_a_id}",
        headers=auth_b,
    )
    assert resp.status_code == 404

    # Org B attempts to read Org A's product via Org A URL path (404 Not Found - non-member)
    resp = await cat_client.get(
        f"/api/organizations/{org_a}/products/{prod_a_id}",
        headers=auth_b,
    )
    assert resp.status_code == 404

    # Org B attempts IDOR via its own Org B URL path with Org A's category ID (404 Not Found)
    resp = await cat_client.get(
        f"/api/organizations/{org_b}/categories/{cat_a_id}",
        headers=auth_b,
    )
    assert resp.status_code == 404

    # Org B attempts IDOR via its own Org B URL path with Org A's product ID (404 Not Found)
    resp = await cat_client.get(
        f"/api/organizations/{org_b}/products/{prod_a_id}",
        headers=auth_b,
    )
    assert resp.status_code == 404

    # Org B cannot assign Org A's category to an Org B product (404 Not Found)
    resp = await cat_client.post(
        f"/api/organizations/{org_b}/products",
        json={
            "code": "WRENCH-01",
            "name": "Adjustable Wrench",
            "base_unit": "piece",
            "default_price_minor": 95000,
            "category_id": cat_a_id,
        },
        headers=auth_b,
    )
    assert resp.status_code == 404

    # Org B can use the identical product code and category name in its own workspace without collision
    cat_b_resp = await cat_client.post(
        f"/api/organizations/{org_b}/categories",
        json={"name": "hardware"},  # Same name, different tenant
        headers=auth_b,
    )
    assert cat_b_resp.status_code == 201

    prod_b_resp = await cat_client.post(
        f"/api/organizations/{org_b}/products",
        json={
            "code": "hammer-01",  # Same code, different tenant
            "name": "Steel Hammer 500g",
            "base_unit": "piece",
            "default_price_minor": 130000,
            "category_id": cat_b_resp.json()["id"],
        },
        headers=auth_b,
    )
    assert prod_b_resp.status_code == 201


@pytest.mark.asyncio
async def test_catalog_rbac_role_matrix(cat_client: AsyncClient) -> None:
    """Verify Owner, Manager, and Staff role enforcement across all catalog operations."""
    _, owner_token = await _create_user(cat_client, "org_owner")
    org_id = await _create_org(cat_client, owner_token, "RBAC Catalog Org")

    # Create Manager and Staff with accepted invitations
    mgr_email, mgr_token = await _create_user(cat_client, "org_mgr")
    await _invite_and_accept(cat_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)

    staff_email, staff_token = await _create_user(cat_client, "org_staff")
    await _invite_and_accept(cat_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    owner_auth = {"Authorization": f"Bearer {owner_token}"}
    mgr_auth = {"Authorization": f"Bearer {mgr_token}"}
    staff_auth = {"Authorization": f"Bearer {staff_token}"}

    # 1. Staff can read catalog
    cat_list = await cat_client.get(
        f"/api/organizations/{org_id}/categories",
        headers=staff_auth,
    )
    assert cat_list.status_code == 200

    prod_list = await cat_client.get(
        f"/api/organizations/{org_id}/products",
        headers=staff_auth,
    )
    assert prod_list.status_code == 200

    # 2. Staff cannot create category (403 Forbidden)
    staff_create_cat = await cat_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Forbidden Category"},
        headers=staff_auth,
    )
    assert staff_create_cat.status_code == 403

    # 3. Staff cannot create product (403 Forbidden)
    staff_create_prod = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "FORBIDDEN-01",
            "name": "Forbidden Product",
            "base_unit": "piece",
            "default_price_minor": 1000,
        },
        headers=staff_auth,
    )
    assert staff_create_prod.status_code == 403

    # 4. Manager can create category and product
    mgr_cat = await cat_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Stationery"},
        headers=mgr_auth,
    )
    assert mgr_cat.status_code == 201
    cat_id = mgr_cat.json()["id"]

    mgr_prod = await cat_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "PEN-001",
            "name": "Blue Ballpoint Pen",
            "base_unit": "piece",
            "default_price_minor": 2500,
            "category_id": cat_id,
        },
        headers=mgr_auth,
    )
    assert mgr_prod.status_code == 201
    prod_id = mgr_prod.json()["id"]

    # 5. Staff cannot update or archive category (403 Forbidden)
    assert (
        await cat_client.patch(
            f"/api/organizations/{org_id}/categories/{cat_id}",
            json={"name": "Office Stationery"},
            headers=staff_auth,
        )
    ).status_code == 403

    assert (
        await cat_client.post(
            f"/api/organizations/{org_id}/categories/{cat_id}/archive",
            headers=staff_auth,
        )
    ).status_code == 403

    # 6. Staff cannot update or archive product (403 Forbidden)
    assert (
        await cat_client.patch(
            f"/api/organizations/{org_id}/products/{prod_id}",
            json={"name": "Black Ballpoint Pen"},
            headers=staff_auth,
        )
    ).status_code == 403

    assert (
        await cat_client.post(
            f"/api/organizations/{org_id}/products/{prod_id}/archive",
            headers=staff_auth,
        )
    ).status_code == 403

    # 7. Owner can update and archive both
    assert (
        await cat_client.patch(
            f"/api/organizations/{org_id}/products/{prod_id}",
            json={"default_price_minor": 3000},
            headers=owner_auth,
        )
    ).status_code == 200

    assert (
        await cat_client.post(
            f"/api/organizations/{org_id}/products/{prod_id}/archive",
            headers=owner_auth,
        )
    ).status_code == 200

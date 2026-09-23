"""Security tests for category tenant isolation, IDOR defense, and RBAC matrix (CAT-001)."""

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


# ==============================================================================
# 1. Cross-Tenant IDOR Defense
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_tenant_idor_read_defense(sec_client: AsyncClient) -> None:
    """Tenant A cannot read Tenant B's category by ID, receiving 404 (IDOR defense)."""
    _, owner_a_token = await _create_user(sec_client, "owner_idor_a")
    org_a = await _create_org(sec_client, owner_a_token, "Org A")

    _, owner_b_token = await _create_user(sec_client, "owner_idor_b")
    org_b = await _create_org(sec_client, owner_b_token, "Org B")

    # Create category in Org B
    cat_b_resp = await sec_client.post(
        f"/api/organizations/{org_b}/categories",
        json={"name": "Org B Category"},
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    assert cat_b_resp.status_code == 201
    cat_b_id = cat_b_resp.json()["id"]

    # Owner A attempts to read Org B's category using Org A's path context -> 404
    read_resp = await sec_client.get(
        f"/api/organizations/{org_a}/categories/{cat_b_id}",
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert read_resp.status_code == 404
    assert read_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Owner A attempts to read Org B's category directly in Org B's path context -> 404 (not a member of Org B)
    direct_resp = await sec_client.get(
        f"/api/organizations/{org_b}/categories/{cat_b_id}",
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert direct_resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_idor_mutation_defense(sec_client: AsyncClient) -> None:
    """Tenant A cannot update or archive Tenant B's category, receiving 404."""
    _, owner_a_token = await _create_user(sec_client, "owner_mut_a")
    org_a = await _create_org(sec_client, owner_a_token, "Org Mut A")

    _, owner_b_token = await _create_user(sec_client, "owner_mut_b")
    org_b = await _create_org(sec_client, owner_b_token, "Org Mut B")

    # Create category in Org B
    cat_b_resp = await sec_client.post(
        f"/api/organizations/{org_b}/categories",
        json={"name": "Org B Secret Category"},
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    assert cat_b_resp.status_code == 201
    cat_b_id = cat_b_resp.json()["id"]

    # Owner A attempts PATCH on Org B's category under Org A -> 404
    patch_resp = await sec_client.patch(
        f"/api/organizations/{org_a}/categories/{cat_b_id}",
        json={"name": "Hacked Name"},
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert patch_resp.status_code == 404

    # Owner A attempts archive on Org B's category under Org A -> 404
    archive_resp = await sec_client.post(
        f"/api/organizations/{org_a}/categories/{cat_b_id}/archive",
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert archive_resp.status_code == 404


# ==============================================================================
# 2. RBAC Matrix Enforcement (Owner vs Manager vs Staff)
# ==============================================================================


@pytest.mark.asyncio
async def test_staff_role_cannot_mutate_categories(sec_client: AsyncClient) -> None:
    """Staff role can read categories but is strictly denied creation, update, and archive (403)."""
    _, owner_token = await _create_user(sec_client, "owner_rbac_staff")
    org_id = await _create_org(sec_client, owner_token, "Staff RBAC Org")

    staff_email, staff_token = await _create_user(sec_client, "staff_user")
    await _invite_and_accept(sec_client, owner_token, org_id, staff_email, staff_token, MemberRole.STAFF)

    # 1. Owner creates an initial category
    cat_resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Hardware"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 2. Staff can read list -> 200
    list_resp = await sec_client.get(
        f"/api/organizations/{org_id}/categories",
        headers=staff_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. Staff can read single category -> 200
    get_resp = await sec_client.get(
        f"/api/organizations/{org_id}/categories/{cat_id}",
        headers=staff_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cat_id

    # 4. Staff CANNOT create category -> 403 Forbidden
    create_resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Staff Category"},
        headers=staff_headers,
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["error"]["code"] == "PERMISSION_DENIED"

    # 5. Staff CANNOT update category -> 403 Forbidden
    update_resp = await sec_client.patch(
        f"/api/organizations/{org_id}/categories/{cat_id}",
        json={"name": "Updated Hardware"},
        headers=staff_headers,
    )
    assert update_resp.status_code == 403
    assert update_resp.json()["error"]["code"] == "PERMISSION_DENIED"

    # 6. Staff CANNOT archive category -> 403 Forbidden
    arch_resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=staff_headers,
    )
    assert arch_resp.status_code == 403
    assert arch_resp.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_manager_role_can_mutate_categories(sec_client: AsyncClient) -> None:
    """Manager role is permitted to create, update, and archive categories."""
    _, owner_token = await _create_user(sec_client, "owner_rbac_mgr")
    org_id = await _create_org(sec_client, owner_token, "Manager RBAC Org")

    mgr_email, mgr_token = await _create_user(sec_client, "mgr_user")
    await _invite_and_accept(sec_client, owner_token, org_id, mgr_email, mgr_token, MemberRole.MANAGER)

    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 1. Manager can create category -> 201
    create_resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Office Supplies"},
        headers=mgr_headers,
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]

    # 2. Manager can update category -> 200
    update_resp = await sec_client.patch(
        f"/api/organizations/{org_id}/categories/{cat_id}",
        json={"name": "Stationery"},
        headers=mgr_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Stationery"

    # 3. Manager can archive category -> 200
    arch_resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=mgr_headers,
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "archived"


# ==============================================================================
# 3. Mass Assignment & Input Tampering Defense
# ==============================================================================


@pytest.mark.asyncio
async def test_mass_assignment_extra_fields_rejected(sec_client: AsyncClient) -> None:
    """Reject payloads containing unapproved fields like organization_id, status, etc."""
    _, token = await _create_user(sec_client, "owner_mass_assign")
    org_id = await _create_org(sec_client, token, "Mass Assign Org")
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to inject organization_id
    resp = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Apparel", "organization_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    # Attempt to inject status
    resp2 = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Footwear", "status": "archived"},
        headers=headers,
    )
    assert resp2.status_code == 422

    # Attempt to inject created_by_user_id
    resp3 = await sec_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Accessories", "created_by_user_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp3.status_code == 422


# ==============================================================================
# 4. Authentication Enforcement
# ==============================================================================


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(sec_client: AsyncClient) -> None:
    """Unauthenticated requests must receive 401 Unauthorized across all category endpoints."""
    fake_org_id = uuid.uuid4()
    fake_cat_id = uuid.uuid4()

    # List
    assert (await sec_client.get(f"/api/organizations/{fake_org_id}/categories")).status_code == 401

    # Get
    assert (await sec_client.get(f"/api/organizations/{fake_org_id}/categories/{fake_cat_id}")).status_code == 401

    # Create
    assert (
        await sec_client.post(
            f"/api/organizations/{fake_org_id}/categories",
            json={"name": "No Auth"},
        )
    ).status_code == 401

    # Update
    assert (
        await sec_client.patch(
            f"/api/organizations/{fake_org_id}/categories/{fake_cat_id}",
            json={"name": "No Auth"},
        )
    ).status_code == 401

    # Archive
    assert (
        await sec_client.post(
            f"/api/organizations/{fake_org_id}/categories/{fake_cat_id}/archive"
        )
    ).status_code == 401

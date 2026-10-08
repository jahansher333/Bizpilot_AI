"""Integration tests for ORG-003 permission model against live PostgreSQL."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
)
from app.modules.organizations.models import OrganizationMember
from app.modules.organizations.permissions import (
    Permission,
    get_role_permissions,
    has_permission,
)


@pytest.fixture
async def perm_client(
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
    """Helper to register and login a user, returning email and access_token."""
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


async def _create_org(client: AsyncClient, token: str, name: str = "Perm Test Org") -> str:
    """Helper to create an organization, returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_owner_membership_resolves_all_permissions_in_db(
    perm_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Active Owner database membership resolves all 39 explicit permissions."""
    _, owner_token = await _create_user(perm_client, "owner_db")
    org_id = await _create_org(perm_client, owner_token, "Owner Perm Org")

    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == uuid.UUID(org_id),
    )
    member = (await db_session.execute(stmt)).scalar_one()

    assert member.role == MemberRole.OWNER.value
    assert member.status == MemberStatus.ACTIVE.value

    perms = get_role_permissions(member.role)
    assert len(perms) == 39
    for p in Permission:
        assert p in perms
        assert has_permission(member.role, p) is True


@pytest.mark.asyncio
async def test_manager_membership_resolves_approved_permissions_in_db(
    perm_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Manager membership resolves approved permissions including Decision 1: correct allowed, void denied."""
    _, owner_token = await _create_user(perm_client, "owner_mgr")
    mgr_email, mgr_token = await _create_user(perm_client, "mgr_user")
    org_id = await _create_org(perm_client, owner_token, "Mgr Perm Org")

    # Invite manager
    resp = await perm_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": mgr_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201

    # The manager accepts; the membership is created active (SEC-P1 F5: invitations are separate)
    accepted = await perm_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    member_id = accepted.json()["id"]
    stmt = select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id))
    member = (await db_session.execute(stmt)).scalar_one()
    assert member.status == MemberStatus.ACTIVE.value

    perms = get_role_permissions(member.role)
    assert len(perms) == 28

    # Founder Decision 1 verification
    assert Permission.ORDERS_CORRECT in perms
    assert Permission.PAYMENTS_CORRECT in perms
    assert Permission.EXPENSES_CORRECT in perms

    assert Permission.ORDERS_VOID not in perms
    assert Permission.PAYMENTS_VOID not in perms
    assert Permission.EXPENSES_VOID not in perms

    # Operational allowed
    assert Permission.PRODUCTS_CREATE in perms
    assert Permission.INVENTORY_ADJUST in perms

    # Org governance denied
    assert Permission.ORG_SETTINGS_UPDATE not in perms
    assert Permission.ORG_MEMBERS_INVITE not in perms
    assert Permission.ORG_MEMBERS_UPDATE_ROLE not in perms
    assert Permission.ORG_MEMBERS_REVOKE not in perms


@pytest.mark.asyncio
async def test_staff_membership_resolves_least_privilege_in_db(
    perm_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Staff membership resolves only least-privilege operations in DB."""
    _, owner_token = await _create_user(perm_client, "owner_stf")
    staff_email, staff_token = await _create_user(perm_client, "staff_user")
    org_id = await _create_org(perm_client, owner_token, "Staff Perm Org")

    resp = await perm_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201
    accepted = await perm_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    member_id = accepted.json()["id"]

    stmt = select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id))
    member = (await db_session.execute(stmt)).scalar_one()

    perms = get_role_permissions(member.role)
    assert len(perms) == 11
    assert Permission.ORDERS_CREATE in perms
    assert Permission.PAYMENTS_CREATE in perms
    assert Permission.CUSTOMERS_CREATE in perms

    # Void and correction are both denied to Staff
    assert Permission.ORDERS_CORRECT not in perms
    assert Permission.ORDERS_VOID not in perms
    assert Permission.INVENTORY_ADJUST not in perms


@pytest.mark.asyncio
async def test_multi_org_isolated_permissions(
    perm_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same user with different roles across organizations resolves distinct permissions per tenant."""
    user_email, user_token = await _create_user(perm_client, "dual_user")
    other_email, other_token = await _create_user(perm_client, "other_owner")

    # User creates Org A -> Owner in Org A
    org_a_id = await _create_org(perm_client, user_token, "Org A")

    # Other user creates Org B -> invites dual_user as Staff
    org_b_id = await _create_org(perm_client, other_token, "Org B")
    invite_resp = await perm_client.post(
        f"/api/organizations/{org_b_id}/members",
        json={"email": user_email, "role": "staff"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert invite_resp.status_code == 201
    accepted_b = await perm_client.post(
        f"/api/organizations/{org_b_id}/members/accept",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    # Fetch User's membership in Org A
    stmt_a = select(OrganizationMember).where(
        OrganizationMember.organization_id == uuid.UUID(org_a_id),
    )
    member_a = (await db_session.execute(stmt_a)).scalar_one()
    assert member_a.role == MemberRole.OWNER.value
    perms_a = get_role_permissions(member_a.role)

    # Fetch User's membership in Org B
    member_b_id = uuid.UUID(accepted_b.json()["id"])
    stmt_b = select(OrganizationMember).where(
        OrganizationMember.id == member_b_id,
    )
    member_b = (await db_session.execute(stmt_b)).scalar_one()
    assert member_b.role == MemberRole.STAFF.value
    perms_b = get_role_permissions(member_b.role)

    # Scoped permissions check
    assert has_permission(member_a.role, Permission.ORG_SETTINGS_UPDATE) is True
    assert has_permission(member_b.role, Permission.ORG_SETTINGS_UPDATE) is False
    assert len(perms_a) == 39
    assert len(perms_b) == 11


@pytest.mark.asyncio
async def test_permission_enforcement_on_member_listing_endpoint(
    perm_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """HTTP endpoint enforces ORG_MEMBERS_READ permission: Owner=200, Manager/Staff=403."""
    _, owner_token = await _create_user(perm_client, "owner_ep")
    mgr_email, mgr_token = await _create_user(perm_client, "mgr_ep")
    staff_email, staff_token = await _create_user(perm_client, "staff_ep")

    org_id = await _create_org(perm_client, owner_token, "Endpoint Perm Org")

    # Invite manager and staff
    m_resp = await perm_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": mgr_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert m_resp.status_code == 201

    s_resp = await perm_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert s_resp.status_code == 201

    # Manager and Staff accept invites so they become active members
    m_acc = await perm_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert m_acc.status_code == 200

    s_acc = await perm_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert s_acc.status_code == 200

    # Owner can list members -> 200
    owner_list = await perm_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_list.status_code == 200

    # Manager cannot list members -> 403 PERMISSION_DENIED
    mgr_list = await perm_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert mgr_list.status_code == 403
    assert mgr_list.json()["error"]["code"] == "PERMISSION_DENIED"

    # Staff cannot list members -> 403 PERMISSION_DENIED
    staff_list = await perm_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_list.status_code == 403
    assert staff_list.json()["error"]["code"] == "PERMISSION_DENIED"

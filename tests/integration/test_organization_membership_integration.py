"""Integration tests for organization membership lifecycle against live PostgreSQL (ORG-002)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.models import User
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember


@pytest.fixture
async def member_client(
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


async def _create_org(client: AsyncClient, token: str, name: str = "Test Org") -> str:
    """Helper to create an organization, returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_owner_can_invite_registered_user(
    member_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify Owner can invite a registered user as Staff."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Invite Org")

    resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "staff"
    assert data["status"] == "invited"
    assert data["email"] == invitee_email

    # Verify in DB
    member_id = uuid.UUID(data["id"])
    stmt = select(OrganizationMember).where(OrganizationMember.id == member_id)
    member = (await db_session.execute(stmt)).scalar_one()
    assert member.role == MemberRole.STAFF.value
    assert member.status == MemberStatus.INVITED.value


@pytest.mark.asyncio
async def test_invite_unregistered_email_returns_404(
    member_client: AsyncClient,
) -> None:
    """Verify inviting unregistered email returns 404 with helpful guidance."""
    _, owner_token = await _create_user(member_client, "owner")
    org_id = await _create_org(member_client, owner_token, "No User Org")

    resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": "nobody_registered@example.com", "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 404
    assert "Please have them register first" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_invite_duplicate_user_returns_409(
    member_client: AsyncClient,
) -> None:
    """Verify inviting a user who already has an invite returns 409 Conflict."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Dupe Org")

    # First invite
    r1 = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r1.status_code == 201

    # Duplicate invite
    r2 = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r2.status_code == 409
    assert "already has a pending invitation" in r2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_invitee_can_accept_invitation(
    member_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify invited user can accept invitation and become active."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, invitee_token = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Accept Org")

    # Invite user
    await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # Accept invitation as invitee
    accept_resp = await member_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
    )
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["status"] == "active"
    assert data["role"] == "staff"

    # Verify in DB
    member_id = uuid.UUID(data["id"])
    stmt = select(OrganizationMember).where(OrganizationMember.id == member_id)
    member = (await db_session.execute(stmt)).scalar_one()
    assert member.status == MemberStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_owner_can_list_members(
    member_client: AsyncClient,
) -> None:
    """Verify Owner can list all organization members."""
    owner_email, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "List Org")

    await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    list_resp = await member_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert len(members) == 2
    roles = {m["role"] for m in members}
    assert "owner" in roles
    assert "manager" in roles


@pytest.mark.asyncio
async def test_owner_can_update_member_role(
    member_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify Owner can change member role from staff to manager."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Role Org")

    inv_resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = inv_resp.json()["id"]

    patch_resp = await member_client.patch(
        f"/api/organizations/{org_id}/members/{member_id}",
        json={"role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "manager"

    # Verify in DB
    stmt = select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id))
    member = (await db_session.execute(stmt)).scalar_one()
    assert member.role == MemberRole.MANAGER.value


@pytest.mark.asyncio
async def test_last_owner_demotion_rejected_with_409(
    member_client: AsyncClient,
) -> None:
    """Verify sole owner cannot be demoted to staff or manager."""
    _, owner_token = await _create_user(member_client, "owner")
    org_id = await _create_org(member_client, owner_token, "Sole Owner Org")

    # Get owner's member ID from list
    list_resp = await member_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_member_id = list_resp.json()[0]["id"]

    patch_resp = await member_client.patch(
        f"/api/organizations/{org_id}/members/{owner_member_id}",
        json={"role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert patch_resp.status_code == 409
    assert "Cannot demote the last owner" in patch_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_multi_owner_demotion_allowed(
    member_client: AsyncClient,
) -> None:
    """Verify owner demotion is permitted when another active owner exists."""
    _, owner1_token = await _create_user(member_client, "owner1")
    owner2_email, owner2_token = await _create_user(member_client, "owner2")
    org_id = await _create_org(member_client, owner1_token, "Dual Owner Org")

    # Owner 1 invites Owner 2 as owner
    inv_resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": owner2_email, "role": "owner"},
        headers={"Authorization": f"Bearer {owner1_token}"},
    )
    assert inv_resp.status_code == 201

    # Owner 2 accepts invite
    await member_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {owner2_token}"},
    )

    # Now there are 2 active owners. Owner 1 demotes self to manager!
    list_resp = await member_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner1_token}"},
    )
    owner1_member_id = [m["id"] for m in list_resp.json() if m["role"] == "owner"][0]

    demote_resp = await member_client.patch(
        f"/api/organizations/{org_id}/members/{owner1_member_id}",
        json={"role": "manager"},
        headers={"Authorization": f"Bearer {owner1_token}"},
    )
    assert demote_resp.status_code == 200
    assert demote_resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_owner_can_revoke_member(
    member_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify Owner can revoke a member's access."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Revoke Org")

    inv_resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = inv_resp.json()["id"]

    del_resp = await member_client.delete(
        f"/api/organizations/{org_id}/members/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "revoked"
    assert del_resp.json()["revoked_at"] is not None

    # Verify in DB
    stmt = select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id))
    member = (await db_session.execute(stmt)).scalar_one()
    assert member.status == MemberStatus.REVOKED.value
    assert member.revoked_at is not None


@pytest.mark.asyncio
async def test_last_owner_revocation_rejected_with_409(
    member_client: AsyncClient,
) -> None:
    """Verify revoking the sole active owner is rejected with 409 Conflict."""
    _, owner_token = await _create_user(member_client, "owner")
    org_id = await _create_org(member_client, owner_token, "Sole Revoke Org")

    list_resp = await member_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_member_id = list_resp.json()[0]["id"]

    del_resp = await member_client.delete(
        f"/api/organizations/{org_id}/members/{owner_member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_resp.status_code == 409
    assert "Cannot revoke the last owner" in del_resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reinviting_revoked_member_succeeds(
    member_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that reinviting a previously revoked user updates status back to invited."""
    _, owner_token = await _create_user(member_client, "owner")
    invitee_email, _ = await _create_user(member_client, "invitee")
    org_id = await _create_org(member_client, owner_token, "Reinvite Org")

    # Invite and revoke
    inv = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    member_id = inv.json()["id"]

    await member_client.delete(
        f"/api/organizations/{org_id}/members/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # Re-invite
    reinv_resp = await member_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert reinv_resp.status_code == 201
    assert reinv_resp.json()["status"] == "invited"
    assert reinv_resp.json()["role"] == "manager"
    assert reinv_resp.json()["revoked_at"] is None

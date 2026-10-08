"""Security and adversarial tests for organization membership and IDOR prevention (ORG-002)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User


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


async def _register_and_login(client: AsyncClient, prefix: str) -> tuple[str, str]:
    """Helper returning email and access token for a freshly registered user."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    resp = await client.post("/api/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200
    return email, resp.json()["access_token"]


async def _create_org(client: AsyncClient, token: str, name: str = "Sec Org") -> str:
    """Helper returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected_401(sec_client: AsyncClient) -> None:
    """Verify all member endpoints reject unauthenticated requests with HTTP 401."""
    random_org_id = uuid.uuid4()
    random_member_id = uuid.uuid4()

    # List members
    r1 = await sec_client.get(f"/api/organizations/{random_org_id}/members")
    assert r1.status_code == 401
    assert r1.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Invite member
    r2 = await sec_client.post(
        f"/api/organizations/{random_org_id}/members",
        json={"email": "nobody@example.com", "role": "staff"},
    )
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Update member role
    r3 = await sec_client.patch(
        f"/api/organizations/{random_org_id}/members/{random_member_id}",
        json={"role": "manager"},
    )
    assert r3.status_code == 401
    assert r3.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Revoke member
    r4 = await sec_client.delete(f"/api/organizations/{random_org_id}/members/{random_member_id}")
    assert r4.status_code == 401
    assert r4.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Accept invite
    r5 = await sec_client.post(f"/api/organizations/{random_org_id}/members/accept")
    assert r5.status_code == 401
    assert r5.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_disabled_user_token_rejected_401(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify token of a disabled user is rejected with HTTP 401."""
    _, token = await _register_and_login(sec_client, "disabled_member")
    org_id = await _create_org(sec_client, token, "Disabled Test Org")

    # Manually disable user in DB
    email_query = select(User).where(User.display_name == "disabled_member User")
    target_user = (await db_session.execute(email_query)).scalars().all()[-1]
    target_user.status = UserStatus.DISABLED.value
    await db_session.commit()

    resp = await sec_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_cross_tenant_idor_member_operations_rejected_404(
    sec_client: AsyncClient,
) -> None:
    """Verify Owner of Org A cannot access or mutate members of Org B."""
    # Org A setup
    _, token_a = await _register_and_login(sec_client, "owner_a")
    org_a = await _create_org(sec_client, token_a, "Org A")

    # Org B setup
    user_b_email, token_b = await _register_and_login(sec_client, "owner_b")
    org_b = await _create_org(sec_client, token_b, "Org B")

    # Org B adds a staff member
    staff_email, staff_b_token = await _register_and_login(sec_client, "staff_b")
    inv_b = await sec_client.post(
        f"/api/organizations/{org_b}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert inv_b.status_code == 201
    accepted_b = await sec_client.post(
        f"/api/organizations/{org_b}/members/accept",
        headers={"Authorization": f"Bearer {staff_b_token}"},
    )
    # A real Org B membership, so the attacks below target an existing record.
    member_b_id = accepted_b.json()["id"]

    # Attack 1: Owner A tries to list members of Org B -> 404 (does not disclose Org B exists)
    r1 = await sec_client.get(
        f"/api/organizations/{org_b}/members",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r1.status_code == 404
    assert r1.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Attack 2: Owner A tries to invite a member to Org B -> 404
    r2 = await sec_client.post(
        f"/api/organizations/{org_b}/members",
        json={"email": "attacker@example.com", "role": "owner"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r2.status_code == 404

    # Attack 3: Owner A tries to mutate role of member in Org B directly -> 404
    r3 = await sec_client.patch(
        f"/api/organizations/{org_b}/members/{member_b_id}",
        json={"role": "staff"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r3.status_code == 404

    # Attack 4: Owner A passes Org A's ID with member_b_id -> 404 (tenant-scoped lookup prevents cross-org mutation)
    r4 = await sec_client.patch(
        f"/api/organizations/{org_a}/members/{member_b_id}",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r4.status_code == 404
    assert "Member not found in organization" in r4.json()["error"]["message"]

    # Attack 5: Owner A tries to revoke member in Org B -> 404
    r5 = await sec_client.delete(
        f"/api/organizations/{org_b}/members/{member_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r5.status_code == 404

    # Attack 6: Owner A passes Org A's ID with member_b_id for revoke -> 404
    r6 = await sec_client.delete(
        f"/api/organizations/{org_a}/members/{member_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r6.status_code == 404
    assert "Member not found in organization" in r6.json()["error"]["message"]


@pytest.mark.asyncio
async def test_privilege_escalation_staff_cannot_manage_members_403(
    sec_client: AsyncClient,
) -> None:
    """Verify active Staff member cannot list, invite, update, or revoke members (403 Forbidden)."""
    _, owner_token = await _register_and_login(sec_client, "owner_priv")
    staff_email, staff_token = await _register_and_login(sec_client, "staff_priv")
    org_id = await _create_org(sec_client, owner_token, "Privilege Test Org")

    # Owner invites staff
    inv_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert inv_resp.status_code == 201

    # Staff accepts invite; the membership ID comes from accepting (SEC-P1 F5)
    accepted = await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    staff_member_id = accepted.json()["id"]

    # 1. Staff attempts to list members -> 403 Forbidden
    r_list = await sec_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_list.status_code == 403
    assert r_list.json()["error"]["code"] == "PERMISSION_DENIED"

    # 2. Staff attempts to invite someone -> 403 Forbidden
    r_inv = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": "friend@example.com", "role": "staff"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_inv.status_code == 403
    assert r_inv.json()["error"]["code"] == "PERMISSION_DENIED"

    # 3. Staff attempts self-promotion to Owner -> 403 Forbidden
    r_patch = await sec_client.patch(
        f"/api/organizations/{org_id}/members/{staff_member_id}",
        json={"role": "owner"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_patch.status_code == 403
    assert r_patch.json()["error"]["code"] == "PERMISSION_DENIED"

    # 4. Staff attempts to revoke a member -> 403 Forbidden
    r_del = await sec_client.delete(
        f"/api/organizations/{org_id}/members/{staff_member_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_del.status_code == 403
    assert r_del.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_revoked_member_immediately_loses_organization_access(
    sec_client: AsyncClient,
) -> None:
    """Verify that once revoked, member loses access on subsequent requests (Security Requirement)."""
    _, owner_token = await _register_and_login(sec_client, "owner_rev_loss")
    staff_email, staff_token = await _register_and_login(sec_client, "staff_rev_loss")
    org_id = await _create_org(sec_client, owner_token, "Revocation Access Org")

    # Invite & accept
    inv_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    accepted = await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    staff_member_id = accepted.json()["id"]

    # Verify staff currently has access to the organization
    get_org_resp = await sec_client.get(
        f"/api/organizations/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert get_org_resp.status_code == 200
    assert get_org_resp.json()["id"] == org_id

    # Owner revokes staff
    del_resp = await sec_client.delete(
        f"/api/organizations/{org_id}/members/{staff_member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "revoked"

    # Subsequent request by revoked staff to the organization MUST be rejected with 404!
    subsequent_resp = await sec_client.get(
        f"/api/organizations/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert subsequent_resp.status_code == 404
    assert subsequent_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

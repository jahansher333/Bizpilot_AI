"""Security, adversarial, and isolation tests for trusted tenant context (ORG-004)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import jwt
import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User
from app.modules.organizations.context import (
    RequestContext,
    get_request_context,
    require_permission,
)
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember
from app.modules.organizations.permissions import Permission

sec_router = APIRouter(prefix="/api/test-sec", tags=["test-security"])


@sec_router.get("/context/{organization_id}")
async def context_route(
    context: RequestContext = Depends(get_request_context),
) -> dict[str, str]:
    return {"status": "ok", "role": context.role.value}


@sec_router.get("/manager-op/{organization_id}")
async def manager_op_route(
    context: RequestContext = Depends(require_permission(Permission.PRODUCTS_CREATE)),
) -> dict[str, str]:
    return {"status": "ok", "operation": "products:create"}


@sec_router.get("/owner-op/{organization_id}")
async def owner_op_route(
    context: RequestContext = Depends(require_permission(Permission.ORDERS_VOID)),
) -> dict[str, str]:
    return {"status": "ok", "operation": "orders:void"}


@pytest.fixture
async def sec_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with test security router and session override."""
    test_app.include_router(sec_router)

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

    login_resp = await client.post("/api/auth/login", json={"email": email, "password": pw})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return email, token


async def _create_org(client: AsyncClient, token: str, name: str = "Sec Org") -> str:
    """Helper to create an organization, returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected_401(sec_client: AsyncClient) -> None:
    """Request without credentials fails with 401 AUTHENTICATION_REQUIRED."""
    random_org_id = uuid.uuid4()
    resp = await sec_client.get(f"/api/test-sec/context/{random_org_id}")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_disabled_user_token_rejected_401(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Disabled user cannot resolve tenant context."""
    user_email, token = await _create_user(sec_client, "disabled_user")
    org_id = await _create_org(ctx_client := sec_client, token, "Disabled User Org")

    # Disable user in DB
    stmt = select(User).where(User.email_normalized == user_email)
    user = (await db_session.execute(stmt)).scalar_one()
    user.status = UserStatus.DISABLED.value
    await db_session.flush()

    resp = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_non_member_access_returns_404(sec_client: AsyncClient) -> None:
    """Non-member access fails with 404 (anti-IDOR non-disclosure)."""
    _, owner_token = await _create_user(sec_client, "owner_a")
    _, stranger_token = await _create_user(sec_client, "stranger")

    org_id = await _create_org(sec_client, owner_token, "Secret Org")

    # Stranger attempts access to Org
    resp = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_invited_membership_returns_404(sec_client: AsyncClient) -> None:
    """Invited membership has zero business permissions and returns 404."""
    _, owner_token = await _create_user(sec_client, "owner_inv")
    invitee_email, invitee_token = await _create_user(sec_client, "invitee")

    org_id = await _create_org(sec_client, owner_token, "Invite Test Org")

    # Invite user as Staff
    await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": invitee_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # Invitee has not accepted invite yet
    resp = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {invitee_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_revoked_membership_returns_404(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Revoked membership immediately returns 404."""
    _, owner_token = await _create_user(sec_client, "owner_rev")
    staff_email, staff_token = await _create_user(sec_client, "staff_rev")

    org_id = await _create_org(sec_client, owner_token, "Revoke Org")

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
    member_id = accepted.json()["id"]  # the membership; the invite ID is the invitation's (SEC-P1 F5)

    # Verify context resolves while active
    r_active = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_active.status_code == 200

    # Owner revokes member
    rev_resp = await sec_client.delete(
        f"/api/organizations/{org_id}/members/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert rev_resp.status_code == 200

    # Subsequent request immediately returns 404
    r_revoked = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_revoked.status_code == 404
    assert r_revoked.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_disabled_organization_returns_404(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Founder Decision 2: Disabled organization returns 404 RESOURCE_NOT_FOUND."""
    _, owner_token = await _create_user(sec_client, "owner_dis_org")
    org_id = await _create_org(sec_client, owner_token, "Disabled Org")

    # Disable organization in DB
    stmt = select(Organization).where(Organization.id == uuid.UUID(org_id))
    org = (await db_session.execute(stmt)).scalar_one()
    org.status = OrganizationStatus.DISABLED.value
    await db_session.flush()

    resp = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_archived_organization_returns_404(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Founder Decision 2: Archived organization returns 404 RESOURCE_NOT_FOUND."""
    _, owner_token = await _create_user(sec_client, "owner_arc_org")
    org_id = await _create_org(sec_client, owner_token, "Archived Org")

    # Archive organization in DB
    stmt = select(Organization).where(Organization.id == uuid.UUID(org_id))
    org = (await db_session.execute(stmt)).scalar_one()
    org.status = OrganizationStatus.ARCHIVED.value
    await db_session.flush()

    resp = await sec_client.get(
        f"/api/test-sec/context/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_forged_jwt_claims_completely_ignored(
    sec_client: AsyncClient,
) -> None:
    """Forged role, permissions, organization_id, and tenant_id claims in JWT are ignored."""
    user_email, legitimate_token = await _create_user(sec_client, "spoof_user")
    _, owner_token = await _create_user(sec_client, "victim_owner")
    org_id = await _create_org(sec_client, owner_token, "Victim Org")

    # User is invited and active as Staff in Victim Org
    await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": user_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {legitimate_token}"},
    )

    # Craft forged JWT with elevated role, permissions, org_id, tenant_id claims
    cfg = get_settings()
    signing_secret = cfg.auth.signing_secret.get_secret_value()
    payload = jwt.decode(
        legitimate_token,
        signing_secret,
        algorithms=["HS256"],
        audience=cfg.auth.jwt_audience,
    )
    spoofed_payload = dict(payload)
    spoofed_payload["role"] = "owner"
    spoofed_payload["permissions"] = ["*"]
    spoofed_payload["organization_id"] = str(uuid.uuid4())
    spoofed_payload["tenant_id"] = str(uuid.uuid4())

    spoofed_token = jwt.encode(spoofed_payload, signing_secret, algorithm="HS256")

    # Attempt Owner-only operation using spoofed token
    resp = await sec_client.get(
        f"/api/test-sec/owner-op/{org_id}",
        headers={"Authorization": f"Bearer {spoofed_token}"},
    )
    # Must be 403 Forbidden because DB role is Staff, regardless of JWT claims
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_require_permission_enforces_rbac_hierarchy(
    sec_client: AsyncClient,
) -> None:
    """require_permission rejects Staff on Manager operations and Manager on Owner operations."""
    _, owner_token = await _create_user(sec_client, "rbac_owner")
    mgr_email, mgr_token = await _create_user(sec_client, "rbac_mgr")
    staff_email, staff_token = await _create_user(sec_client, "rbac_staff")

    org_id = await _create_org(sec_client, owner_token, "RBAC Org")

    # Invite and accept Manager
    await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": mgr_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )

    # Invite and accept Staff
    await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )

    # 1. Staff requests Manager operation (products:create) -> 403
    r_staff_mgr = await sec_client.get(
        f"/api/test-sec/manager-op/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert r_staff_mgr.status_code == 403
    assert r_staff_mgr.json()["error"]["code"] == "PERMISSION_DENIED"

    # 2. Manager requests Manager operation -> 200
    r_mgr_mgr = await sec_client.get(
        f"/api/test-sec/manager-op/{org_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r_mgr_mgr.status_code == 200

    # 3. Manager requests Owner-only operation (orders:void) -> 403
    r_mgr_owner = await sec_client.get(
        f"/api/test-sec/owner-op/{org_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert r_mgr_owner.status_code == 403
    assert r_mgr_owner.json()["error"]["code"] == "PERMISSION_DENIED"

    # 4. Owner requests Owner operation -> 200
    r_owner_owner = await sec_client.get(
        f"/api/test-sec/owner-op/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r_owner_owner.status_code == 200


@pytest.mark.asyncio
async def test_role_downgrade_takes_immediate_effect(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Demoting Manager to Staff immediately revokes Manager operation access on next request."""
    _, owner_token = await _create_user(sec_client, "owner_dg2")
    user_email, user_token = await _create_user(sec_client, "target_mgr")

    org_id = await _create_org(sec_client, owner_token, "Downgrade Org")

    # Invite as Manager & accept
    inv_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": user_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    accepted = await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    member_id = accepted.json()["id"]  # the membership; the invite ID is the invitation's (SEC-P1 F5)

    # Manager can access manager operation -> 200
    r1 = await sec_client.get(
        f"/api/test-sec/manager-op/{org_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r1.status_code == 200

    # Owner demotes member to Staff
    patch_resp = await sec_client.patch(
        f"/api/organizations/{org_id}/members/{member_id}",
        json={"role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "staff"

    # Next request immediately receives 403 Forbidden without waiting for token expiry
    r2 = await sec_client.get(
        f"/api/test-sec/manager-op/{org_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == "PERMISSION_DENIED"

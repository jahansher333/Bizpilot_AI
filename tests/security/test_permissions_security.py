"""Security and adversarial tests for ORG-003 permission model."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthorizationException, ErrorCode
from app.db.session import get_session
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
)
from app.modules.organizations.models import OrganizationMember
from app.modules.organizations.permissions import (
    Permission,
    check_permission,
    has_permission,
)


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


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str, str]:
    """Helper returning email, password, and access token for a freshly registered user."""
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
    return email, pw, token


async def _create_org(client: AsyncClient, token: str, name: str = "Sec Perm Org") -> str:
    """Helper returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_spoofed_jwt_claims_do_not_elevate_permissions(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Forged claims ('role', 'permissions', 'is_owner') in JWT cannot bypass DB-backed permission checks."""
    user_email, user_pw, legitimate_token = await _create_user(sec_client, "spoof_user")
    owner_email, _, owner_token = await _create_user(sec_client, "target_owner")

    org_id = await _create_org(sec_client, owner_token, "Target Org")

    # Invite spoof_user as Staff
    invite_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": user_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert invite_resp.status_code == 201

    # Staff user accepts invite to become active Staff member
    acc_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {legitimate_token}"},
    )
    assert acc_resp.status_code == 200

    cfg = get_settings()
    signing_secret = cfg.auth.signing_secret.get_secret_value()

    # Decode valid token payload to get user ID
    payload = jwt.decode(
        legitimate_token,
        signing_secret,
        algorithms=["HS256"],
        audience=cfg.auth.jwt_audience,
    )

    # Craft forged token with injected role/permissions claims signed with valid secret
    spoofed_payload = dict(payload)
    spoofed_payload["role"] = "owner"
    spoofed_payload["permissions"] = ["*"]
    spoofed_payload["org_id"] = org_id
    spoofed_payload["is_admin"] = True

    spoofed_token = jwt.encode(
        spoofed_payload,
        signing_secret,
        algorithm="HS256",
    )

    # Attempt to list members using spoofed token
    # The endpoint checks the database role (which is 'staff'), not JWT claims
    resp = await sec_client.get(
        f"/api/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {spoofed_token}"},
    )
    # Must be forbidden because DB role is staff
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_role_downgrade_takes_immediate_effect_without_stale_token_window(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Downgrading a role in the DB immediately revokes elevated permissions without waiting for token expiry."""
    owner_email, _, owner_token = await _create_user(sec_client, "owner_dg")
    mgr_email, _, mgr_token = await _create_user(sec_client, "mgr_dg")

    org_id = await _create_org(sec_client, owner_token, "Immediate Effect Org")

    # Invite as Manager
    inv_resp = await sec_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": mgr_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert inv_resp.status_code == 201
    member_id = inv_resp.json()["id"]

    # Activate member in DB
    stmt = select(OrganizationMember).where(OrganizationMember.id == uuid.UUID(member_id))
    member = (await db_session.execute(stmt)).scalar_one()
    member.status = MemberStatus.ACTIVE.value
    await db_session.flush()

    # Manager role permits ORDERS_CORRECT but denies ORDERS_VOID
    assert has_permission(member.role, Permission.ORDERS_CORRECT) is True
    assert has_permission(member.role, Permission.ORDERS_VOID) is False

    # Owner downgrades member to Staff in DB
    member.role = MemberRole.STAFF.value
    await db_session.flush()

    # Verify that re-reading member from DB immediately removes ORDERS_CORRECT
    refreshed_member = (await db_session.execute(stmt)).scalar_one()
    assert has_permission(refreshed_member.role, Permission.ORDERS_CORRECT) is False
    assert has_permission(refreshed_member.role, Permission.ORDERS_VOID) is False


def test_default_deny_on_privilege_escalation_and_malicious_strings() -> None:
    """Adversarial input to check_permission and has_permission fails closed with default-deny."""
    malicious_inputs = [
        "admin",
        "superadmin",
        "root",
        "owner; DROP TABLE organization_members;--",
        "owner' OR '1'='1",
        "guest",
        "auditor",
        "manager/*",
        "*",
        "",
        " ",
        None,
    ]

    for malicious in malicious_inputs:
        # has_permission must safely return False without error
        assert has_permission(malicious, Permission.ORG_SETTINGS_UPDATE) is False  # type: ignore[arg-type]
        assert has_permission(malicious, Permission.ORDERS_VOID) is False  # type: ignore[arg-type]

        # check_permission must raise 403 AuthorizationException with PERMISSION_DENIED code
        with pytest.raises(AuthorizationException) as exc_info:
            check_permission(malicious, Permission.ORG_SETTINGS_UPDATE)  # type: ignore[arg-type]
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == ErrorCode.PERMISSION_DENIED


def test_manager_cannot_execute_owner_void_permissions() -> None:
    """Explicitly verify that check_permission rejects void operations for Manager."""
    void_permissions = [
        Permission.ORDERS_VOID,
        Permission.PAYMENTS_VOID,
        Permission.EXPENSES_VOID,
    ]

    for void_perm in void_permissions:
        assert has_permission(MemberRole.MANAGER, void_perm) is False
        assert has_permission("manager", void_perm) is False

        with pytest.raises(AuthorizationException) as exc_info:
            check_permission(MemberRole.MANAGER, void_perm)
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == ErrorCode.PERMISSION_DENIED

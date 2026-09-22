"""Integration tests for trusted tenant context resolution against live PostgreSQL (ORG-004)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.organizations.context import (
    RequestContext,
    get_request_context,
)
from app.modules.organizations.enums import MemberRole

# Minimal test-only router to verify dependency execution
context_test_router = APIRouter(prefix="/api/test-context", tags=["test-context"])


@context_test_router.get("/path/{organization_id}")
async def path_endpoint(
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return {
        "organization_id": str(context.organization_id),
        "user_id": str(context.user_id),
        "role": context.role.value,
        "permissions_count": len(context.permissions),
        "membership_id": str(context.membership_id),
    }


@context_test_router.get("/header")
async def header_endpoint(
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return {
        "organization_id": str(context.organization_id),
        "user_id": str(context.user_id),
        "role": context.role.value,
        "permissions_count": len(context.permissions),
        "membership_id": str(context.membership_id),
    }


@context_test_router.get("/precedence/{organization_id}")
async def precedence_endpoint(
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return {
        "organization_id": str(context.organization_id),
        "role": context.role.value,
    }


@pytest.fixture
async def ctx_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with test routes and session override."""
    # Mount test routes
    test_app.include_router(context_test_router)

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


async def _create_org(client: AsyncClient, token: str, name: str = "Context Org") -> str:
    """Helper to create an organization, returning organization ID."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_active_owner_context_resolution(ctx_client: AsyncClient) -> None:
    """Active Owner resolves trusted context with full permissions."""
    _, owner_token = await _create_user(ctx_client, "owner_ctx")
    org_id = await _create_org(ctx_client, owner_token, "Owner Workspace")

    resp = await ctx_client.get(
        f"/api/test-context/path/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["organization_id"] == org_id
    assert data["role"] == MemberRole.OWNER.value
    assert data["permissions_count"] == 39


@pytest.mark.asyncio
async def test_active_manager_context_resolution(ctx_client: AsyncClient) -> None:
    """Active Manager resolves trusted context with 28 approved permissions."""
    _, owner_token = await _create_user(ctx_client, "owner_for_mgr")
    mgr_email, mgr_token = await _create_user(ctx_client, "mgr_user")
    org_id = await _create_org(ctx_client, owner_token, "Mgr Workspace")

    # Invite manager
    inv_resp = await ctx_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": mgr_email, "role": "manager"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert inv_resp.status_code == 201

    # Manager accepts invite
    acc_resp = await ctx_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert acc_resp.status_code == 200

    # Resolve context
    resp = await ctx_client.get(
        f"/api/test-context/path/{org_id}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["organization_id"] == org_id
    assert data["role"] == MemberRole.MANAGER.value
    assert data["permissions_count"] == 28


@pytest.mark.asyncio
async def test_active_staff_context_resolution(ctx_client: AsyncClient) -> None:
    """Active Staff resolves trusted context with 11 least-privilege permissions."""
    _, owner_token = await _create_user(ctx_client, "owner_for_staff")
    staff_email, staff_token = await _create_user(ctx_client, "staff_user")
    org_id = await _create_org(ctx_client, owner_token, "Staff Workspace")

    # Invite staff
    inv_resp = await ctx_client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": staff_email, "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert inv_resp.status_code == 201

    # Staff accepts invite
    acc_resp = await ctx_client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert acc_resp.status_code == 200

    # Resolve context
    resp = await ctx_client.get(
        f"/api/test-context/path/{org_id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["organization_id"] == org_id
    assert data["role"] == MemberRole.STAFF.value
    assert data["permissions_count"] == 11


@pytest.mark.asyncio
async def test_header_selector_resolution(ctx_client: AsyncClient) -> None:
    """Context resolves from X-Organization-ID header when path parameter is absent."""
    _, owner_token = await _create_user(ctx_client, "owner_hdr")
    org_id = await _create_org(ctx_client, owner_token, "Header Workspace")

    resp = await ctx_client.get(
        "/api/test-context/header",
        headers={
            "Authorization": f"Bearer {owner_token}",
            "X-Organization-ID": org_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["organization_id"] == org_id
    assert data["role"] == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_path_precedence_over_header_live(ctx_client: AsyncClient) -> None:
    """Founder Decision 1: When both path and header exist, PATH WINS without comparing."""
    _, user_token = await _create_user(ctx_client, "dual_owner")
    org_path = await _create_org(ctx_client, user_token, "Path Workspace")
    org_header = await _create_org(ctx_client, user_token, "Header Workspace")

    resp = await ctx_client.get(
        f"/api/test-context/precedence/{org_path}",
        headers={
            "Authorization": f"Bearer {user_token}",
            "X-Organization-ID": org_header,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Path takes absolute precedence
    assert data["organization_id"] == org_path


@pytest.mark.asyncio
async def test_multi_org_isolated_context(ctx_client: AsyncClient) -> None:
    """User who is Owner in Org 1 and Staff in Org 2 resolves distinct contexts per selector."""
    user_email, user_token = await _create_user(ctx_client, "cross_user")
    other_email, other_token = await _create_user(ctx_client, "org2_owner")

    # User creates Org 1 -> Owner
    org1_id = await _create_org(ctx_client, user_token, "Workspace One")

    # Other user creates Org 2 -> invites cross_user as Staff
    org2_id = await _create_org(ctx_client, other_token, "Workspace Two")
    inv_resp = await ctx_client.post(
        f"/api/organizations/{org2_id}/members",
        json={"email": user_email, "role": "staff"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert inv_resp.status_code == 201

    # Accept invite in Org 2
    acc_resp = await ctx_client.post(
        f"/api/organizations/{org2_id}/members/accept",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert acc_resp.status_code == 200

    # Query Org 1 -> must be Owner (39 perms)
    r1 = await ctx_client.get(
        f"/api/test-context/path/{org1_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["role"] == MemberRole.OWNER.value
    assert r1.json()["permissions_count"] == 39

    # Query Org 2 -> must be Staff (11 perms)
    r2 = await ctx_client.get(
        f"/api/test-context/path/{org2_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["role"] == MemberRole.STAFF.value
    assert r2.json()["permissions_count"] == 11

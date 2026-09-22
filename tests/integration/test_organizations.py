"""Integration tests for organizations and initial membership against live PostgreSQL (ORG-001)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.models import User
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember
from app.modules.organizations.repository import OrganizationRepository


@pytest.fixture
async def org_client(
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


async def _create_registered_user(client: AsyncClient, email_prefix: str) -> tuple[str, str, str]:
    """Helper to register and login a user, returning email, password, and access_token."""
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": "Test User"},
    )
    assert reg_resp.status_code == 202

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return email, pw, token


@pytest.mark.asyncio
async def test_organization_creation_persists_org_and_owner_membership(
    org_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify POST /api/organizations creates exactly 1 organization and 1 founding owner membership."""
    _, _, token = await _create_registered_user(org_client, "owner")

    resp = await org_client.post(
        "/api/organizations",
        json={
            "display_name": "Bismillah Superstore",
            "currency_code": "pkr",
            "timezone": "Asia/Karachi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()

    org_id = uuid.UUID(body["id"])
    assert body["display_name"] == "Bismillah Superstore"
    assert body["currency_code"] == "PKR"
    assert body["timezone"] == "Asia/Karachi"
    assert body["status"] == "active"
    assert body["role"] == "owner"

    # Verify DB state: organization
    stmt_org = select(Organization).where(Organization.id == org_id)
    org_row = (await db_session.execute(stmt_org)).scalar_one()
    assert org_row.display_name == "Bismillah Superstore"
    assert org_row.currency_code == "PKR"
    assert org_row.timezone == "Asia/Karachi"
    assert org_row.status == OrganizationStatus.ACTIVE.value

    # Verify DB state: founding membership
    stmt_mem = select(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    members = (await db_session.execute(stmt_mem)).scalars().all()
    assert len(members) == 1
    founding_member = members[0]
    assert founding_member.role == MemberRole.OWNER.value
    assert founding_member.status == MemberStatus.ACTIVE.value
    assert founding_member.invited_by_user_id is None


@pytest.mark.asyncio
async def test_atomic_rollback_on_membership_failure_leaves_no_orphan_org(
    db_session: AsyncSession,
) -> None:
    """Verify that if member insertion fails, the entire transaction rolls back with 0 orphan organizations."""
    repo = OrganizationRepository(db_session)
    non_existent_user_id = uuid.uuid4()

    # Attempt to create organization and member referencing non-existent user_id (FK violation)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            org = await repo.create_organization(
                display_name="Orphan Candidate Org",
            )
            # This triggers FK violation on users(id)
            await repo.create_member(
                organization_id=org.id,
                user_id=non_existent_user_id,
                role=MemberRole.OWNER.value,
            )

    # Verify zero organizations with that display name survived
    stmt = select(Organization).where(Organization.display_name == "Orphan Candidate Org")
    surviving_orgs = (await db_session.execute(stmt)).scalars().all()
    assert len(surviving_orgs) == 0, "Orphan organization survived failed membership transaction!"


@pytest.mark.asyncio
async def test_composite_unique_constraint_rejects_duplicate_membership(
    db_session: AsyncSession,
) -> None:
    """Verify DB constraint uq_organization_members_org_user rejects duplicate membership for same user."""
    repo = OrganizationRepository(db_session)

    # Create real user in DB
    user = User(
        email_normalized=f"unique_mem_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Unique User",
    )
    db_session.add(user)
    await db_session.flush()

    org = await repo.create_organization(display_name="Unique Membership Org")
    await repo.create_member(organization_id=org.id, user_id=user.id, role="owner")

    # Attempt duplicate insert within savepoint
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await repo.create_member(organization_id=org.id, user_id=user.id, role="manager")


@pytest.mark.asyncio
async def test_foreign_key_delete_restrict_prevents_unsafe_deletion(
    db_session: AsyncSession,
) -> None:
    """Verify RESTRICT foreign key prevents deleting a user or organization with active memberships."""
    repo = OrganizationRepository(db_session)

    user = User(
        email_normalized=f"fk_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="FK User",
    )
    db_session.add(user)
    await db_session.flush()

    org = await repo.create_organization(display_name="FK Org")
    await repo.create_member(organization_id=org.id, user_id=user.id, role="owner")

    # Attempt deleting user -> blocked by FK constraint
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(user)
            await db_session.flush()

    # Attempt deleting organization -> blocked by FK constraint
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(org)
            await db_session.flush()


@pytest.mark.asyncio
async def test_multi_organization_same_user_and_cross_user_listing(
    org_client: AsyncClient,
) -> None:
    """Verify:
    1. User A can create and belong to multiple organizations (Org A1, Org A2).
    2. User B creates Org B1.
    3. User A list contains Org A1 and Org A2, and does NOT contain Org B1.
    4. User B list contains Org B1 only.
    """
    _, _, token_a = await _create_registered_user(org_client, "user_a")
    _, _, token_b = await _create_registered_user(org_client, "user_b")

    # User A creates two organizations
    r_a1 = await org_client.post(
        "/api/organizations",
        json={"display_name": "User A First Store"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_a1.status_code == 201
    id_a1 = r_a1.json()["id"]

    r_a2 = await org_client.post(
        "/api/organizations",
        json={"display_name": "User A Second Branch"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_a2.status_code == 201
    id_a2 = r_a2.json()["id"]

    # User B creates one organization
    r_b1 = await org_client.post(
        "/api/organizations",
        json={"display_name": "User B Pharmacy"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r_b1.status_code == 201
    id_b1 = r_b1.json()["id"]

    # User A lists organizations
    list_a = await org_client.get("/api/organizations", headers={"Authorization": f"Bearer {token_a}"})
    assert list_a.status_code == 200
    list_a_data = list_a.json()
    org_ids_a = {item["id"] for item in list_a_data}
    assert id_a1 in org_ids_a
    assert id_a2 in org_ids_a
    assert id_b1 not in org_ids_a

    # User B lists organizations
    list_b = await org_client.get("/api/organizations", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    list_b_data = list_b.json()
    org_ids_b = {item["id"] for item in list_b_data}
    assert id_b1 in org_ids_b
    assert id_a1 not in org_ids_b
    assert id_a2 not in org_ids_b

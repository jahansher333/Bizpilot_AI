"""Integration tests for ScopedRepository against live PostgreSQL (ORG-005)."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.auth.models import User
from app.modules.organizations.enums import MemberRole, MemberStatus, OrganizationStatus
from app.modules.organizations.models import Organization, OrganizationMember


async def _create_test_user(session: AsyncSession, prefix: str) -> User:
    """Helper to persist a user entity in the database."""
    user = User(
        email_normalized=f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        display_name=f"{prefix} Name",
        status="active",
    )
    session.add(user)
    await session.flush()
    return user


async def _create_test_org(session: AsyncSession, name: str) -> Organization:
    """Helper to persist an organization entity in the database."""
    org = Organization(
        display_name=name,
        currency_code="PKR",
        timezone="Asia/Karachi",
        status=OrganizationStatus.ACTIVE.value,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_member(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MemberRole = MemberRole.STAFF,
) -> OrganizationMember:
    """Helper to persist an organization member entity in the database."""
    member = OrganizationMember(
        organization_id=org_id,
        user_id=user_id,
        role=role.value,
        status=MemberStatus.ACTIVE.value,
    )
    session.add(member)
    await session.flush()
    return member


@pytest.mark.asyncio
async def test_get_by_id_tenant_isolation(db_session: AsyncSession) -> None:
    """Tenant A can retrieve its own record, but cannot retrieve Tenant B's record."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    user_a = await _create_test_user(db_session, "user_a")
    user_b = await _create_test_user(db_session, "user_b")

    member_a = await _create_test_member(db_session, org_a.id, user_a.id, MemberRole.OWNER)
    member_b = await _create_test_member(db_session, org_b.id, user_b.id, MemberRole.STAFF)

    repo_a = ScopedRepository(
        session=db_session,
        organization_id=org_a.id,
        model_cls=OrganizationMember,
    )

    # 1. Retrieve own record in Tenant A -> succeeds
    retrieved_a = await repo_a.get_by_id(member_a.id)
    assert retrieved_a is not None
    assert retrieved_a.id == member_a.id
    assert retrieved_a.organization_id == org_a.id

    # 2. Attempt to retrieve Tenant B record using Tenant A repo -> returns None
    retrieved_b = await repo_a.get_by_id(member_b.id)
    assert retrieved_b is None


@pytest.mark.asyncio
async def test_nonexistent_vs_cross_tenant_observable_equivalence(db_session: AsyncSession) -> None:
    """Nonexistent UUID returns identical None result as a cross-tenant resource UUID."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    user_b = await _create_test_user(db_session, "user_b")
    member_b = await _create_test_member(db_session, org_b.id, user_b.id)

    repo_a = ScopedRepository(
        session=db_session,
        organization_id=org_a.id,
        model_cls=OrganizationMember,
    )

    # Cross-tenant ID
    cross_tenant_res = await repo_a.get_by_id(member_b.id)
    assert cross_tenant_res is None

    # Completely random, non-existent UUID
    nonexistent_id = uuid.uuid4()
    nonexistent_res = await repo_a.get_by_id(nonexistent_id)
    assert nonexistent_res is None

    # Both produce exactly None (anti-enumeration)
    assert cross_tenant_res == nonexistent_res


@pytest.mark.asyncio
async def test_list_scoped_isolation(db_session: AsyncSession) -> None:
    """list_scoped in Tenant A returns all and only Tenant A records."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    user_a1 = await _create_test_user(db_session, "user_a1")
    user_a2 = await _create_test_user(db_session, "user_a2")
    user_b1 = await _create_test_user(db_session, "user_b1")

    member_a1 = await _create_test_member(db_session, org_a.id, user_a1.id, MemberRole.OWNER)
    member_a2 = await _create_test_member(db_session, org_a.id, user_a2.id, MemberRole.STAFF)
    member_b1 = await _create_test_member(db_session, org_b.id, user_b1.id, MemberRole.OWNER)

    repo_a = ScopedRepository(
        session=db_session,
        organization_id=org_a.id,
        model_cls=OrganizationMember,
    )
    repo_b = ScopedRepository(
        session=db_session,
        organization_id=org_b.id,
        model_cls=OrganizationMember,
    )

    # List Org A records
    records_a = await repo_a.list_scoped()
    ids_a = {r.id for r in records_a}
    assert member_a1.id in ids_a
    assert member_a2.id in ids_a
    assert member_b1.id not in ids_a

    # List Org B records
    records_b = await repo_b.list_scoped()
    ids_b = {r.id for r in records_b}
    assert member_b1.id in ids_b
    assert member_a1.id not in ids_b
    assert member_a2.id not in ids_b


@pytest.mark.asyncio
async def test_validate_tenant_relationship_same_vs_cross_tenant(db_session: AsyncSession) -> None:
    """validate_tenant_relationship succeeds for same tenant and fails for cross-tenant target."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    user_a = await _create_test_user(db_session, "user_a")
    user_b = await _create_test_user(db_session, "user_b")

    member_a = await _create_test_member(db_session, org_a.id, user_a.id)
    member_b = await _create_test_member(db_session, org_b.id, user_b.id)

    repo_a = ScopedRepository(session=db_session, organization_id=org_a.id)

    # Same-tenant relationship -> True
    assert (
        await repo_a.validate_tenant_relationship(
            related_id=member_a.id,
            model_cls=OrganizationMember,
        )
        is True
    )

    # Cross-tenant relationship -> False
    assert (
        await repo_a.validate_tenant_relationship(
            related_id=member_b.id,
            model_cls=OrganizationMember,
        )
        is False
    )

    # Nonexistent target -> False
    assert (
        await repo_a.validate_tenant_relationship(
            related_id=uuid.uuid4(),
            model_cls=OrganizationMember,
        )
        is False
    )


@pytest.mark.asyncio
async def test_multi_org_user_remains_strictly_scoped(db_session: AsyncSession) -> None:
    """A user who is a member of both Org A and Org B only sees the records of the scoped repository."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    shared_user = await _create_test_user(db_session, "shared_user")

    member_in_a = await _create_test_member(db_session, org_a.id, shared_user.id, MemberRole.OWNER)
    member_in_b = await _create_test_member(db_session, org_b.id, shared_user.id, MemberRole.STAFF)

    # Repository instantiated for Org A
    repo_a = ScopedRepository(
        session=db_session,
        organization_id=org_a.id,
        model_cls=OrganizationMember,
    )

    # In Org A repo, member_in_a exists
    record_a = await repo_a.get_by_id(member_in_a.id)
    assert record_a is not None
    assert record_a.role == MemberRole.OWNER.value

    # In Org A repo, member_in_b does NOT exist (None)
    record_b = await repo_a.get_by_id(member_in_b.id)
    assert record_b is None

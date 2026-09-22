"""Security tests for ScopedRepository and tenant isolation invariants (ORG-005)."""

from __future__ import annotations

import inspect
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


def test_absence_of_unrestricted_id_only_lookup_api() -> None:
    """ScopedRepository must NOT expose any public lookup method by ID alone without tenant context."""
    public_methods = [
        name for name, func in inspect.getmembers(ScopedRepository, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]

    # Forbidden method names that imply unscoped lookups
    forbidden_names = {"get", "find", "get_unscoped", "find_by_id", "all", "get_all"}
    for method_name in public_methods:
        assert method_name not in forbidden_names, f"Forbidden unscoped method found: {method_name}"

    # Verify that get_by_id operates within the bound organization_id
    sig = inspect.signature(ScopedRepository.get_by_id)
    assert "resource_id" in sig.parameters


def test_tenant_rebinding_invariant() -> None:
    """ScopedRepository prohibits re-binding organization_id after instantiation."""
    mock_session = object()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    repo = ScopedRepository(session=mock_session, organization_id=org_a)  # type: ignore[arg-type]

    # Attempting to assign to public property
    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo.organization_id = org_b  # type: ignore[misc]

    # Attempting to assign to internal attribute
    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo._organization_id = org_b

    # Verify still bound to original org
    assert repo.organization_id == org_a


@pytest.mark.asyncio
async def test_idor_resource_id_rejection(db_session: AsyncSession) -> None:
    """Adversary attempting IDOR with Tenant B's UUID in Tenant A repository gets None (no leakage)."""
    org_victim = await _create_test_org(db_session, "Victim Org")
    org_attacker = await _create_test_org(db_session, "Attacker Org")

    user_victim = await _create_test_user(db_session, "victim")
    user_attacker = await _create_test_user(db_session, "attacker")

    victim_member = await _create_test_member(
        db_session, org_victim.id, user_victim.id, MemberRole.OWNER
    )
    await _create_test_member(
        db_session, org_attacker.id, user_attacker.id, MemberRole.OWNER
    )

    attacker_repo = ScopedRepository(
        session=db_session,
        organization_id=org_attacker.id,
        model_cls=OrganizationMember,
    )

    # Attacker specifies victim's known member ID
    res = await attacker_repo.get_by_id(victim_member.id)
    assert res is None, "CRITICAL: IDOR vulnerability! Cross-tenant entity was returned."


@pytest.mark.asyncio
async def test_two_organization_strict_isolation(db_session: AsyncSession) -> None:
    """Two organizations with similar resources remain strictly isolated in lists and queries."""
    org_1 = await _create_test_org(db_session, "Company 1")
    org_2 = await _create_test_org(db_session, "Company 2")

    u1 = await _create_test_user(db_session, "c1_user")
    u2 = await _create_test_user(db_session, "c2_user")

    m1 = await _create_test_member(db_session, org_1.id, u1.id, MemberRole.OWNER)
    m2 = await _create_test_member(db_session, org_2.id, u2.id, MemberRole.OWNER)

    repo_1 = ScopedRepository(session=db_session, organization_id=org_1.id, model_cls=OrganizationMember)
    repo_2 = ScopedRepository(session=db_session, organization_id=org_2.id, model_cls=OrganizationMember)

    list_1 = await repo_1.list_scoped()
    list_2 = await repo_2.list_scoped()

    assert len(list_1) >= 1
    assert len(list_2) >= 1

    ids_1 = {m.id for m in list_1}
    ids_2 = {m.id for m in list_2}

    # Strict disjointness
    assert m1.id in ids_1
    assert m1.id not in ids_2
    assert m2.id in ids_2
    assert m2.id not in ids_1
    assert ids_1.isdisjoint(ids_2)


@pytest.mark.asyncio
async def test_cross_tenant_relationship_forgery_rejection(db_session: AsyncSession) -> None:
    """Attempting to forge a foreign key link to another tenant's resource is caught by relationship check."""
    org_legit = await _create_test_org(db_session, "Legit Org")
    org_foreign = await _create_test_org(db_session, "Foreign Org")

    user_foreign = await _create_test_user(db_session, "foreign_user")
    foreign_member = await _create_test_member(db_session, org_foreign.id, user_foreign.id)

    legit_repo = ScopedRepository(session=db_session, organization_id=org_legit.id)

    # Verify that foreign_member cannot be claimed as a relationship in org_legit
    is_valid = await legit_repo.validate_tenant_relationship(
        related_id=foreign_member.id,
        model_cls=OrganizationMember,
    )
    assert is_valid is False, "CRITICAL: Foreign tenant resource accepted in relationship validation."


@pytest.mark.asyncio
async def test_nonexistent_and_cross_tenant_nondisclosure(db_session: AsyncSession) -> None:
    """Security property: Cross-tenant ID and random non-existent ID yield identical repository outcome."""
    org = await _create_test_org(db_session, "Target Org")
    other_org = await _create_test_org(db_session, "Other Org")

    other_user = await _create_test_user(db_session, "other")
    other_member = await _create_test_member(db_session, other_org.id, other_user.id)

    repo = ScopedRepository(session=db_session, organization_id=org.id, model_cls=OrganizationMember)

    fake_id = uuid.uuid4()
    real_foreign_id = other_member.id

    res_fake = await repo.get_by_id(fake_id)
    res_foreign = await repo.get_by_id(real_foreign_id)

    assert res_fake is None
    assert res_foreign is None
    # No distinguishing characteristics between missing and cross-tenant
    assert res_fake == res_foreign

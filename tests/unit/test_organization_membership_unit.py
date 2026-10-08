"""Unit tests for Organization Membership schemas and Service (ORG-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.errors import (
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    NotFoundException,
)
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.enums import (
    InvitationStatus,
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import INVITATION_TTL, Organization, OrganizationInvitation, OrganizationMember
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    InviteMemberRequest,
    OrganizationMemberResponse,
    UpdateMemberRoleRequest,
)
from app.modules.organizations.service import OrganizationService


# ==============================================================================
# SCHEMA & VALIDATION TESTS
# ==============================================================================


def test_invite_member_schema_defaults() -> None:
    """Verify default role is staff when not specified."""
    req = InviteMemberRequest(email="staff@example.com")
    assert req.email == "staff@example.com"
    assert req.role == MemberRole.STAFF


def test_invite_member_schema_explicit_roles() -> None:
    """Verify owner, manager, staff roles are all valid."""
    for role_val in (MemberRole.OWNER, MemberRole.MANAGER, MemberRole.STAFF):
        req = InviteMemberRequest(email="user@example.com", role=role_val)
        assert req.role == role_val


def test_invite_member_schema_invalid_role() -> None:
    """Verify invalid role string is rejected."""
    with pytest.raises(ValidationError):
        InviteMemberRequest(email="user@example.com", role="superadmin")  # type: ignore[arg-type]


def test_invite_member_schema_invalid_email() -> None:
    """Verify invalid email format is rejected."""
    with pytest.raises(ValidationError):
        InviteMemberRequest(email="not-an-email")


def test_invite_member_schema_extra_fields_forbidden() -> None:
    """Verify unexpected fields are rejected by extra='forbid'."""
    with pytest.raises(ValidationError):
        InviteMemberRequest(email="user@example.com", is_admin=True)  # type: ignore[call-arg]


def test_update_member_role_schema_valid_and_invalid() -> None:
    """Verify UpdateMemberRoleRequest validates role properly."""
    req = UpdateMemberRoleRequest(role=MemberRole.MANAGER)
    assert req.role == MemberRole.MANAGER

    with pytest.raises(ValidationError):
        UpdateMemberRoleRequest(role="invalid_role")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        UpdateMemberRoleRequest(role=MemberRole.STAFF, extra="forbidden")  # type: ignore[call-arg]


# ==============================================================================
# SERVICE UNIT TESTS
# ==============================================================================


def _make_active_user(user_id: uuid.UUID | None = None, role: str = "owner") -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id or uuid.uuid4(),
        email_normalized="test@example.com",
        display_name="Test User",
        status=UserStatus.ACTIVE.value,
    )


def _make_org_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = MemberRole.OWNER.value,
    status: str = MemberStatus.ACTIVE.value,
) -> OrganizationMember:
    now = datetime.now(timezone.utc)
    return OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user_id,
        role=role,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _make_user_entity(user_id: uuid.UUID, email: str = "target@example.com") -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_id,
        email_normalized=email,
        display_name="Target User",
        status=UserStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_members_success_for_owner() -> None:
    """Verify active Owner can list members."""
    org_id = uuid.uuid4()
    owner_user = _make_active_user()
    owner_member = _make_org_member(org_id, owner_user.id, role=MemberRole.OWNER.value)

    target_user_id = uuid.uuid4()
    target_user = _make_user_entity(target_user_id)
    target_member = _make_org_member(org_id, target_user_id, role=MemberRole.STAFF.value)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = owner_member
    mock_repo.list_members.return_value = [
        (owner_member, _make_user_entity(owner_user.id, email="owner@example.com")),
        (target_member, target_user),
    ]

    service = OrganizationService(session=mock_session, repository=mock_repo)
    result = await service.list_members(org_id, owner_user)

    assert len(result) == 2
    assert result[0].role == "owner"
    assert result[1].role == "staff"
    assert result[1].email == "target@example.com"


@pytest.mark.asyncio
async def test_list_members_forbidden_for_manager_and_staff() -> None:
    """Verify active Manager or Staff receives 403 Forbidden when listing members (Founder Decision 1)."""
    org_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)

    for non_owner_role in (MemberRole.MANAGER.value, MemberRole.STAFF.value):
        user = _make_active_user(role=non_owner_role)
        member = _make_org_member(org_id, user.id, role=non_owner_role)
        mock_repo.get_member.return_value = member

        service = OrganizationService(session=mock_session, repository=mock_repo)
        with pytest.raises(AuthorizationException):
            await service.list_members(org_id, user)


@pytest.mark.asyncio
async def test_list_members_not_found_for_outsider() -> None:
    """Verify outsider caller receives 404 Not Found when attempting to list members of unjoined org."""
    org_id = uuid.uuid4()
    outsider = _make_active_user()

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = None

    service = OrganizationService(session=mock_session, repository=mock_repo)
    with pytest.raises(NotFoundException):
        await service.list_members(org_id, outsider)


def _make_invitation(
    org_id: uuid.UUID,
    email: str = "invitee@example.com",
    role: str = MemberRole.STAFF.value,
    expires_in: timedelta = timedelta(days=7),
) -> OrganizationInvitation:
    now = datetime.now(timezone.utc)
    return OrganizationInvitation(
        id=uuid.uuid4(),
        organization_id=org_id,
        email_normalized=email,
        role=role,
        status=InvitationStatus.PENDING.value,
        created_at=now,
        updated_at=now,
        expires_at=now + expires_in,
    )


def _invite_repo(owner_member: OrganizationMember) -> AsyncMock:
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_member.return_value = owner_member
    repo.get_active_member_by_email.return_value = None
    repo.get_pending_invitation_for_email.return_value = None
    return repo


@pytest.mark.asyncio
async def test_invite_member_creates_email_invitation_with_seven_day_expiry() -> None:
    """Owner invites an email address; no account lookup is involved (SEC-P1 F5)."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    mock_repo = _invite_repo(_make_org_member(org_id, owner.id, role=MemberRole.OWNER.value))
    mock_repo.create_invitation.side_effect = lambda **kw: _make_invitation(
        org_id, email=kw["email_normalized"], role=kw["role"], expires_in=kw["expires_at"] - datetime.now(timezone.utc)
    )

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    resp = await service.invite_member(org_id, owner, InviteMemberRequest(email="Invitee@Example.com", role=MemberRole.STAFF))

    assert resp.status == "pending"
    assert resp.role == "staff"
    assert resp.email == "invitee@example.com"
    kwargs = mock_repo.create_invitation.await_args.kwargs
    assert kwargs["email_normalized"] == "invitee@example.com"
    assert timedelta(days=6, hours=23) < kwargs["expires_at"] - datetime.now(timezone.utc) <= INVITATION_TTL
    mock_repo.get_user_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_member_response_shape_never_depends_on_accounts() -> None:
    """The response model carries no account fields at all, so it cannot leak account existence."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    mock_repo = _invite_repo(_make_org_member(org_id, owner.id, role=MemberRole.OWNER.value))
    mock_repo.create_invitation.return_value = _make_invitation(org_id, email="someone@example.com")

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    resp = await service.invite_member(org_id, owner, InviteMemberRequest(email="someone@example.com", role=MemberRole.STAFF))

    assert "user_id" not in resp.model_dump()
    assert "display_name" not in resp.model_dump()


@pytest.mark.asyncio
async def test_invite_member_already_active_rejected_409() -> None:
    """Inviting a current member of this organization is a conflict (owners already see members)."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    mock_repo = _invite_repo(_make_org_member(org_id, owner.id, role=MemberRole.OWNER.value))
    mock_repo.get_active_member_by_email.return_value = _make_org_member(org_id, uuid.uuid4())

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    with pytest.raises(ConflictException) as exc_info:
        await service.invite_member(org_id, owner, InviteMemberRequest(email="target@example.com", role=MemberRole.STAFF))

    assert "already a member" in str(exc_info.value.message)
    mock_repo.create_invitation.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_member_reinvite_updates_role_and_renews_expiry() -> None:
    """Re-inviting an email with an open invitation updates it instead of failing."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    mock_repo = _invite_repo(_make_org_member(org_id, owner.id, role=MemberRole.OWNER.value))
    existing = _make_invitation(org_id, role=MemberRole.STAFF.value, expires_in=timedelta(days=-1))
    mock_repo.get_pending_invitation_for_email.return_value = existing

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    resp = await service.invite_member(org_id, owner, InviteMemberRequest(email="invitee@example.com", role=MemberRole.MANAGER))

    assert resp.id == str(existing.id)
    assert existing.role == "manager"
    assert existing.expires_at > datetime.now(timezone.utc) + timedelta(days=6)
    mock_repo.create_invitation.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_member_role_last_owner_demotion_blocked() -> None:
    """Verify demoting sole owner to manager/staff is blocked by 409 Conflict."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)
    user_entity = _make_user_entity(owner.id)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = owner_member
    mock_repo.get_member_by_id.return_value = (owner_member, user_entity)
    mock_repo.count_active_owners.return_value = 1  # only 1 owner!

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = UpdateMemberRoleRequest(role=MemberRole.MANAGER)
    with pytest.raises(ConflictException) as exc_info:
        await service.update_member_role(org_id, owner_member.id, owner, req)

    assert "Cannot demote the last owner" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_update_member_role_multi_owner_demotion_allowed() -> None:
    """Verify demoting owner succeeds when multiple owners exist."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)
    user_entity = _make_user_entity(owner.id)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = owner_member
    mock_repo.get_member_by_id.return_value = (owner_member, user_entity)
    mock_repo.count_active_owners.return_value = 2  # 2 active owners

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = UpdateMemberRoleRequest(role=MemberRole.MANAGER)
    resp = await service.update_member_role(org_id, owner_member.id, owner, req)

    assert resp.role == "manager"


@pytest.mark.asyncio
async def test_revoke_member_last_owner_revocation_blocked() -> None:
    """Verify revoking sole active owner is blocked by 409 Conflict."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)
    user_entity = _make_user_entity(owner.id)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = owner_member
    mock_repo.get_member_by_id.return_value = (owner_member, user_entity)
    mock_repo.count_active_owners.return_value = 1

    service = OrganizationService(session=mock_session, repository=mock_repo)
    with pytest.raises(ConflictException) as exc_info:
        await service.revoke_member(org_id, owner_member.id, owner)

    assert "Cannot revoke the last owner" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_accept_invitation_success() -> None:
    """The invitee accepts the invitation addressed to their own email; a membership is created."""
    org_id = uuid.uuid4()
    invitee = _make_active_user()
    invitation = _make_invitation(org_id, email=invitee.email_normalized)
    created_member = _make_org_member(org_id, invitee.id, role=MemberRole.STAFF.value)

    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_pending_invitation_for_email.return_value = invitation
    mock_repo.get_organization_by_id.return_value = Organization(id=org_id, display_name="Org", status="active")
    mock_repo.get_member.return_value = None
    mock_repo.create_member.return_value = created_member

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    resp = await service.accept_invitation(org_id, invitee)

    assert resp.status == "active"
    assert invitation.status == InvitationStatus.ACCEPTED.value
    assert invitation.accepted_by_user_id == invitee.id
    mock_repo.get_pending_invitation_for_email.assert_awaited_once_with(org_id, invitee.email_normalized, for_update=True)


@pytest.mark.asyncio
async def test_accept_expired_invitation_is_not_found() -> None:
    org_id = uuid.uuid4()
    invitee = _make_active_user()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_pending_invitation_for_email.return_value = _make_invitation(
        org_id, email=invitee.email_normalized, expires_in=timedelta(seconds=-1)
    )
    mock_repo.get_organization_by_id.return_value = Organization(id=org_id, display_name="Org", status="active")

    service = OrganizationService(session=AsyncMock(), repository=mock_repo)
    with pytest.raises(NotFoundException):
        await service.accept_invitation(org_id, invitee)
    mock_repo.create_member.assert_not_awaited()

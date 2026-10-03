"""Unit tests for Organization Membership schemas and Service (ORG-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember
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


@pytest.mark.asyncio
async def test_invite_member_success() -> None:
    """Verify Owner can invite a registered user."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)

    target_id = uuid.uuid4()
    target_user = _make_user_entity(target_id, email="invitee@example.com")
    new_member = _make_org_member(org_id, target_id, role=MemberRole.STAFF.value, status=MemberStatus.INVITED.value)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.side_effect = [owner_member, None]  # first caller check, second target check
    mock_repo.get_user_by_email.return_value = target_user
    mock_repo.create_member.return_value = new_member

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = InviteMemberRequest(email="invitee@example.com", role=MemberRole.STAFF)
    resp = await service.invite_member(org_id, owner, req)

    assert resp.status == "invited"
    assert resp.role == "staff"
    assert resp.email == "invitee@example.com"
    mock_repo.create_member.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_member_unregistered_user_rejected_404() -> None:
    """Verify inviting unregistered email returns 404 with registration guidance (Founder Decision 2)."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.return_value = owner_member
    mock_repo.get_user_by_email.return_value = None

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = InviteMemberRequest(email="nonexistent@example.com", role=MemberRole.STAFF)
    with pytest.raises(NotFoundException) as exc_info:
        await service.invite_member(org_id, owner, req)

    assert "register first" in str(exc_info.value.message)
    assert "nonexistent@example.com" not in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_invite_member_inactive_user_gets_same_message_as_missing() -> None:
    """Missing and inactive accounts must be indistinguishable to the inviting owner (FIX-006)."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)
    inactive_target = _make_user_entity(uuid.uuid4())
    inactive_target.status = "disabled"

    messages = []
    for target in (None, inactive_target):
        mock_repo = AsyncMock(spec=OrganizationRepository)
        mock_repo.get_member.return_value = owner_member
        mock_repo.get_user_by_email.return_value = target
        service = OrganizationService(session=AsyncMock(), repository=mock_repo)
        with pytest.raises(NotFoundException) as exc_info:
            await service.invite_member(
                org_id, owner, InviteMemberRequest(email="someone@example.com", role=MemberRole.STAFF)
            )
        messages.append(exc_info.value.message)

    assert messages[0] == messages[1]


@pytest.mark.asyncio
async def test_invite_member_already_active_rejected_409() -> None:
    """Verify inviting already active member returns 409 Conflict."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)

    target_id = uuid.uuid4()
    target_user = _make_user_entity(target_id)
    existing_active = _make_org_member(org_id, target_id, status=MemberStatus.ACTIVE.value)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.side_effect = [owner_member, existing_active]
    mock_repo.get_user_by_email.return_value = target_user

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = InviteMemberRequest(email="target@example.com", role=MemberRole.STAFF)
    with pytest.raises(ConflictException) as exc_info:
        await service.invite_member(org_id, owner, req)

    assert "already an active member" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_invite_member_already_invited_rejected_409() -> None:
    """Verify inviting user who already has pending invitation returns 409 Conflict."""
    org_id = uuid.uuid4()
    owner = _make_active_user()
    owner_member = _make_org_member(org_id, owner.id, role=MemberRole.OWNER.value)

    target_id = uuid.uuid4()
    target_user = _make_user_entity(target_id)
    existing_invited = _make_org_member(org_id, target_id, status=MemberStatus.INVITED.value)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_member.side_effect = [owner_member, existing_invited]
    mock_repo.get_user_by_email.return_value = target_user

    service = OrganizationService(session=mock_session, repository=mock_repo)
    req = InviteMemberRequest(email="target@example.com", role=MemberRole.STAFF)
    with pytest.raises(ConflictException) as exc_info:
        await service.invite_member(org_id, owner, req)

    assert "already has a pending invitation" in str(exc_info.value.message)


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
    """Verify invited user can accept their pending invitation."""
    org_id = uuid.uuid4()
    invitee = _make_active_user()
    invitee_member = _make_org_member(org_id, invitee.id, role=MemberRole.STAFF.value, status=MemberStatus.INVITED.value)
    invitee_user = _make_user_entity(invitee.id)

    mock_session = AsyncMock()
    mock_repo = AsyncMock(spec=OrganizationRepository)
    mock_repo.get_pending_invitation.return_value = (invitee_member, invitee_user)

    service = OrganizationService(session=mock_session, repository=mock_repo)
    resp = await service.accept_invitation(org_id, invitee)

    assert resp.status == "active"
    assert invitee_member.status == MemberStatus.ACTIVE.value

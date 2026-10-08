"""Domain service orchestrating organization and membership operations (ORG-001, ORG-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    NotFoundException,
)
from app.modules.auth.enums import UserStatus
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.enums import (
    InvitationStatus,
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import INVITATION_TTL, OrganizationInvitation, OrganizationMember
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    InvitationResponse,
    InviteMemberRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    PendingInvitationResponse,
    UpdateMemberRoleRequest,
)
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.service import InternalTraceService


class OrganizationService:
    """Domain service managing organization workspace lifecycle and initial membership."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[OrganizationRepository] = None,
    ) -> None:
        self._session = session
        self._repository = repository or OrganizationRepository(session)

    async def _trace_membership(
        self,
        action: TraceAction,
        member: OrganizationMember,
        actor_user_id: uuid.UUID,
        metadata: dict[str, str],
    ) -> None:
        """FR-003: record membership changes in internal traceability (no emails stored)."""
        await InternalTraceService(self._session, member.organization_id).record_event(
            action=action,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="organization_member",
            target_id=member.id,
            metadata={"member_user_id": str(member.user_id), **metadata},
        )

    async def create_organization(
        self,
        current_user: AuthenticatedUser,
        request: CreateOrganizationRequest,
    ) -> OrganizationResponse:
        """Atomically create a new organization and founding owner membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        # Atomic persistence: organization + owner membership in single transaction
        org = await self._repository.create_organization(
            display_name=request.display_name,
            currency_code=request.currency_code,
            timezone=request.timezone,
            status=OrganizationStatus.ACTIVE.value,
        )

        member = await self._repository.create_member(
            organization_id=org.id,
            user_id=current_user.id,
            role=MemberRole.OWNER.value,
            status=MemberStatus.ACTIVE.value,
            invited_by_user_id=None,
        )

        return OrganizationResponse(
            id=str(org.id),
            display_name=org.display_name,
            currency_code=org.currency_code,
            timezone=org.timezone,
            status=org.status,
            created_at=org.created_at,
            role=member.role,
        )

    async def get_organization(
        self,
        current_user: AuthenticatedUser,
        organization_id: uuid.UUID,
    ) -> OrganizationResponse:
        """Retrieve organization details strictly scoped to caller's active membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        row = await self._repository.get_organization_with_active_membership(
            organization_id=organization_id,
            user_id=current_user.id,
        )
        if row is None:
            raise NotFoundException("Organization not found")

        org, member = row
        return OrganizationResponse(
            id=str(org.id),
            display_name=org.display_name,
            currency_code=org.currency_code,
            timezone=org.timezone,
            status=org.status,
            created_at=org.created_at,
            role=member.role,
        )

    async def list_organizations(
        self,
        current_user: AuthenticatedUser,
    ) -> list[OrganizationResponse]:
        """List all organizations where caller has an active membership."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        rows = await self._repository.list_user_organizations_with_active_memberships(
            user_id=current_user.id
        )
        return [
            OrganizationResponse(
                id=str(org.id),
                display_name=org.display_name,
                currency_code=org.currency_code,
                timezone=org.timezone,
                status=org.status,
                created_at=org.created_at,
                role=member.role,
            )
            for org, member in rows
        ]

    async def _verify_active_owner(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> OrganizationMember:
        """Verify that caller has an active owner membership in the specified organization."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        member = await self._repository.get_member(
            organization_id=organization_id,
            user_id=current_user.id,
        )
        if member is None or member.status != MemberStatus.ACTIVE.value:
            raise NotFoundException("Organization not found")

        check_permission(member.role, Permission.ORG_MEMBERS_READ)

        return member

    async def list_members(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> list[OrganizationMemberResponse]:
        """List all members of an organization, restricted to active Owners."""
        await self._verify_active_owner(organization_id, current_user)
        rows = await self._repository.list_members(organization_id)
        return [
            OrganizationMemberResponse(
                id=str(member.id),
                organization_id=str(member.organization_id),
                user_id=str(member.user_id),
                role=member.role,
                status=member.status,
                invited_by_user_id=str(member.invited_by_user_id) if member.invited_by_user_id else None,
                created_at=member.created_at,
                updated_at=member.updated_at,
                revoked_at=member.revoked_at,
                email=user.email_normalized,
                display_name=user.display_name,
            )
            for member, user in rows
        ]

    @staticmethod
    def _invitation_response(invitation: OrganizationInvitation) -> InvitationResponse:
        return InvitationResponse(
            id=str(invitation.id),
            organization_id=str(invitation.organization_id),
            email=invitation.email_normalized,
            role=invitation.role,
            status=invitation.status,
            invited_by_user_id=str(invitation.invited_by_user_id) if invitation.invited_by_user_id else None,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
            expires_at=invitation.expires_at,
        )

    async def _trace_invitation(
        self,
        action: TraceAction,
        invitation: OrganizationInvitation,
        actor_user_id: uuid.UUID,
        metadata: dict[str, str],
    ) -> None:
        """FR-003: record invitation changes in internal traceability (no emails stored)."""
        await InternalTraceService(self._session, invitation.organization_id).record_event(
            action=action,
            outcome=TraceOutcome.SUCCESS,
            actor_user_id=actor_user_id,
            target_type="organization_invitation",
            target_id=invitation.id,
            metadata=metadata,
        )

    async def invite_member(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: InviteMemberRequest,
    ) -> InvitationResponse:
        """Invite any well-formed email address (SEC-P1 F5).

        The response never depends on whether the email has a BizPilot account, so the invite
        form cannot be used to enumerate accounts. Re-inviting an email that already has a
        pending invitation updates its role, renews its 7-day expiry and returns it.
        """
        await self._verify_active_owner(organization_id, current_user)
        email_normalized = str(request.email).strip().lower()

        # Membership of this organization is already visible to its owners in the members list,
        # so saying so reveals nothing about the wider account base.
        if await self._repository.get_active_member_by_email(organization_id, email_normalized):
            raise ConflictException("This person is already a member of this workspace")

        invitation = await self._repository.get_pending_invitation_for_email(
            organization_id, email_normalized, for_update=True
        )
        now = datetime.now(timezone.utc)
        if invitation is None:
            invitation = await self._repository.create_invitation(
                organization_id=organization_id,
                email_normalized=email_normalized,
                role=request.role.value,
                invited_by_user_id=current_user.id,
                expires_at=now + INVITATION_TTL,
            )
        else:
            # Also revives an expired invitation: it is still the one open row for this email.
            invitation.role = request.role.value
            invitation.invited_by_user_id = current_user.id
            invitation.updated_at = now
            invitation.expires_at = now + INVITATION_TTL
            await self._session.flush()

        await self._trace_invitation(
            TraceAction.ORG_MEMBER_INVITED, invitation, current_user.id, {"role": invitation.role}
        )
        return self._invitation_response(invitation)

    async def list_invitations(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> list[InvitationResponse]:
        """List the organization's pending invitations, restricted to active Owners."""
        await self._verify_active_owner(organization_id, current_user)
        rows = await self._repository.list_pending_invitations(organization_id, datetime.now(timezone.utc))
        return [self._invitation_response(invitation) for invitation in rows]

    async def revoke_invitation(
        self,
        organization_id: uuid.UUID,
        invitation_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> InvitationResponse:
        """Cancel a pending invitation, restricted to active Owners."""
        await self._verify_active_owner(organization_id, current_user)
        invitation = await self._repository.get_invitation(organization_id, invitation_id)
        if invitation is None:
            raise NotFoundException("Invitation not found in organization")
        if invitation.status != InvitationStatus.PENDING.value:
            raise ConflictException("Only pending invitations can be revoked")

        now = datetime.now(timezone.utc)
        invitation.status = InvitationStatus.REVOKED.value
        invitation.revoked_at = now
        invitation.updated_at = now
        await self._session.flush()
        await self._trace_invitation(
            TraceAction.ORG_MEMBER_REVOKED, invitation, current_user.id, {"role": invitation.role}
        )
        return self._invitation_response(invitation)

    async def update_member_role(
        self,
        organization_id: uuid.UUID,
        member_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: UpdateMemberRoleRequest,
    ) -> OrganizationMemberResponse:
        """Update an organization member's role with last-owner protection."""
        await self._verify_active_owner(organization_id, current_user)

        row = await self._repository.get_member_by_id(organization_id, member_id)
        if row is None:
            raise NotFoundException("Member not found in organization")

        member, user = row
        if member.status == MemberStatus.REVOKED.value:
            raise ConflictException("Cannot change role of a revoked member")

        # Last-owner demotion check
        if member.role == MemberRole.OWNER.value and request.role.value != MemberRole.OWNER.value:
            active_owners = await self._repository.count_active_owners(organization_id, for_update=True)
            if active_owners <= 1:
                raise ConflictException("Cannot demote the last owner of the organization")

        previous_role = member.role
        member.role = request.role.value
        member.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        if previous_role != member.role:
            await self._trace_membership(
                TraceAction.ORG_MEMBER_ROLE_CHANGED,
                member,
                current_user.id,
                {"previous_role": previous_role, "role": member.role},
            )

        return OrganizationMemberResponse(
            id=str(member.id),
            organization_id=str(member.organization_id),
            user_id=str(member.user_id),
            role=member.role,
            status=member.status,
            invited_by_user_id=str(member.invited_by_user_id) if member.invited_by_user_id else None,
            created_at=member.created_at,
            updated_at=member.updated_at,
            revoked_at=member.revoked_at,
            email=user.email_normalized,
            display_name=user.display_name,
        )

    async def revoke_member(
        self,
        organization_id: uuid.UUID,
        member_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> OrganizationMemberResponse:
        """Revoke an organization member's access with last-owner protection."""
        await self._verify_active_owner(organization_id, current_user)

        row = await self._repository.get_member_by_id(organization_id, member_id)
        if row is None:
            raise NotFoundException("Member not found in organization")

        member, user = row
        if member.status != MemberStatus.REVOKED.value:
            # Last-owner revocation check
            if member.role == MemberRole.OWNER.value and member.status == MemberStatus.ACTIVE.value:
                active_owners = await self._repository.count_active_owners(organization_id, for_update=True)
                if active_owners <= 1:
                    raise ConflictException("Cannot revoke the last owner of the organization")

            previous_status = member.status
            member.status = MemberStatus.REVOKED.value
            member.revoked_at = datetime.now(timezone.utc)
            member.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            await self._trace_membership(
                TraceAction.ORG_MEMBER_REVOKED,
                member,
                current_user.id,
                {"role": member.role, "previous_status": previous_status},
            )

        return OrganizationMemberResponse(
            id=str(member.id),
            organization_id=str(member.organization_id),
            user_id=str(member.user_id),
            role=member.role,
            status=member.status,
            invited_by_user_id=str(member.invited_by_user_id) if member.invited_by_user_id else None,
            created_at=member.created_at,
            updated_at=member.updated_at,
            revoked_at=member.revoked_at,
            email=user.email_normalized,
            display_name=user.display_name,
        )

    async def list_my_invitations(
        self,
        current_user: AuthenticatedUser,
    ) -> list[PendingInvitationResponse]:
        """List pending invitations addressed to the caller's email (FIX-006, SEC-P1 F5)."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        rows = await self._repository.list_pending_invitations_for_email(
            current_user.email_normalized, datetime.now(timezone.utc)
        )
        return [
            PendingInvitationResponse(
                invitation_id=str(invitation.id),
                organization_id=str(org.id),
                organization_display_name=org.display_name,
                role=invitation.role,
                invited_at=invitation.updated_at,
            )
            for invitation, org in rows
        ]

    async def accept_invitation(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> OrganizationMemberResponse:
        """Accept the pending invitation addressed to the caller's email."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        invitation = await self._repository.get_pending_invitation_for_email(
            organization_id, current_user.email_normalized, for_update=True
        )
        organization = await self._repository.get_organization_by_id(organization_id)
        now = datetime.now(timezone.utc)
        if (
            invitation is None
            or invitation.expires_at <= now
            or organization is None
            or organization.status != OrganizationStatus.ACTIVE.value
        ):
            raise NotFoundException("No pending invitation found for this organization")

        member = await self._repository.get_member(organization_id, current_user.id)
        if member is None:
            member = await self._repository.create_member(
                organization_id=organization_id,
                user_id=current_user.id,
                role=invitation.role,
                status=MemberStatus.ACTIVE.value,
                invited_by_user_id=invitation.invited_by_user_id,
            )
        elif member.status != MemberStatus.ACTIVE.value:
            # A previously removed member rejoins with the role this invitation offers.
            member.status = MemberStatus.ACTIVE.value
            member.role = invitation.role
            member.invited_by_user_id = invitation.invited_by_user_id
            member.revoked_at = None
            member.updated_at = now

        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_by_user_id = current_user.id
        invitation.accepted_at = now
        invitation.updated_at = now
        await self._session.flush()
        await self._trace_membership(
            TraceAction.ORG_MEMBER_ACCEPTED, member, current_user.id, {"role": member.role}
        )

        return OrganizationMemberResponse(
            id=str(member.id),
            organization_id=str(member.organization_id),
            user_id=str(member.user_id),
            role=member.role,
            status=member.status,
            invited_by_user_id=str(member.invited_by_user_id) if member.invited_by_user_id else None,
            created_at=member.created_at,
            updated_at=member.updated_at,
            revoked_at=member.revoked_at,
            email=current_user.email_normalized,
            display_name=current_user.display_name,
        )

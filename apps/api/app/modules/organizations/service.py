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
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import OrganizationMember
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
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

    async def invite_member(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
        request: InviteMemberRequest,
    ) -> OrganizationMemberResponse:
        """Invite a registered user to join the organization."""
        await self._verify_active_owner(organization_id, current_user)

        target_user = await self._repository.get_user_by_email(request.email)
        if target_user is None or target_user.status != UserStatus.ACTIVE.value:
            # One message for missing and inactive accounts; never echo the email or account state.
            raise NotFoundException(
                "No active BizPilot account was found for this email. "
                "Ask them to register first, then send the invitation again."
            )

        existing_member = await self._repository.get_member(organization_id, target_user.id)
        if existing_member is not None:
            if existing_member.status == MemberStatus.ACTIVE.value:
                raise ConflictException("User is already an active member of this organization")
            elif existing_member.status == MemberStatus.INVITED.value:
                raise ConflictException("User already has a pending invitation to this organization")
            elif existing_member.status == MemberStatus.REVOKED.value:
                existing_member.status = MemberStatus.INVITED.value
                existing_member.role = request.role.value
                existing_member.invited_by_user_id = current_user.id
                existing_member.revoked_at = None
                existing_member.updated_at = datetime.now(timezone.utc)
                await self._session.flush()
                member = existing_member
            else:
                member = existing_member
        else:
            member = await self._repository.create_member(
                organization_id=organization_id,
                user_id=target_user.id,
                role=request.role.value,
                status=MemberStatus.INVITED.value,
                invited_by_user_id=current_user.id,
            )

        await self._trace_membership(
            TraceAction.ORG_MEMBER_INVITED, member, current_user.id, {"role": member.role}
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
            email=target_user.email_normalized,
            display_name=target_user.display_name,
        )

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
        """List pending invitations addressed to the caller (FIX-006)."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        rows = await self._repository.list_pending_invitations_for_user(current_user.id)
        return [
            PendingInvitationResponse(
                membership_id=str(member.id),
                organization_id=str(org.id),
                organization_display_name=org.display_name,
                role=member.role,
                invited_at=member.updated_at,
            )
            for member, org in rows
        ]

    async def accept_invitation(
        self,
        organization_id: uuid.UUID,
        current_user: AuthenticatedUser,
    ) -> OrganizationMemberResponse:
        """Accept a pending invitation to an organization."""
        if current_user.status != UserStatus.ACTIVE.value:
            raise AuthenticationException("User account is inactive or disabled")

        row = await self._repository.get_pending_invitation(organization_id, current_user.id)
        if row is None:
            raise NotFoundException("No pending invitation found for this organization")

        member, user = row
        member.status = MemberStatus.ACTIVE.value
        member.updated_at = datetime.now(timezone.utc)
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
            email=user.email_normalized,
            display_name=user.display_name,
        )

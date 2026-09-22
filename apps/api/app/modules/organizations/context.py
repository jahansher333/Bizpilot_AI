"""Trusted tenant context data structures and FastAPI dependencies (ORG-004).

Builds immutable request context containing authenticated user, verified active
organization, membership ID, persisted role, and derived operation permissions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    NotFoundException,
    ValidationException,
)
from app.db.session import get_session
from app.modules.auth.tokens import AuthenticatedUser, get_current_user
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.permissions import (
    Permission,
    check_permission,
    get_role_permissions,
    has_permission,
)
from app.modules.organizations.repository import OrganizationRepository


@dataclass(frozen=True)
class OrganizationContext:
    """Immutable representation of the resolved organization tenant."""

    id: uuid.UUID
    display_name: str
    currency_code: str
    timezone: str
    status: str


@dataclass(frozen=True)
class RequestContext:
    """Immutable, trusted request context for tenant-scoped operations."""

    user: AuthenticatedUser
    organization: OrganizationContext
    membership_id: uuid.UUID
    role: MemberRole

    @property
    def organization_id(self) -> uuid.UUID:
        """Convenience property for tenant ID."""
        return self.organization.id

    @property
    def user_id(self) -> uuid.UUID:
        """Convenience property for caller user ID."""
        return self.user.id

    @property
    def permissions(self) -> frozenset[Permission]:
        """Derive permission set on demand from verified role."""
        return get_role_permissions(self.role)

    def has_permission(self, permission: Permission) -> bool:
        """Check whether caller holds an explicit operation permission."""
        return has_permission(self.role, permission)

    def check_permission(self, permission: Permission) -> None:
        """Assert permission or raise 403 AuthorizationException."""
        check_permission(self.role, permission)


def extract_organization_selector(request: Request) -> uuid.UUID:
    """Extract untrusted organization selector following strict precedence:
    1. path_params['organization_id']
    2. Header: 'x-organization-id' (case-insensitive)

    Path parameter takes absolute precedence over header.
    Query parameters, request body, and JWT claims are strictly ignored.
    """
    raw_selector: str | None = None

    # 1. Path parameter check (precedence)
    if "organization_id" in request.path_params:
        raw_selector = str(request.path_params["organization_id"])
    else:
        # 2. Header fallback
        header_val = request.headers.get("x-organization-id")
        if header_val:
            raw_selector = header_val

    if not raw_selector or not raw_selector.strip():
        raise ValidationException("Organization context required")

    try:
        return uuid.UUID(raw_selector.strip())
    except (ValueError, TypeError, AttributeError):
        raise ValidationException("Invalid organization selector format")


async def get_request_context(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RequestContext:
    """FastAPI dependency resolving trusted RequestContext from verified DB membership."""
    organization_id = extract_organization_selector(request)

    repo = OrganizationRepository(session)
    row = await repo.get_organization_with_active_membership(
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if row is None:
        raise NotFoundException("Organization not found")

    org, member = row

    if org.status != OrganizationStatus.ACTIVE.value:
        raise NotFoundException("Organization not found")

    if member.status != MemberStatus.ACTIVE.value:
        raise NotFoundException("Organization not found")

    try:
        member_role = MemberRole(member.role)
    except (ValueError, KeyError):
        raise NotFoundException("Organization not found")

    org_context = OrganizationContext(
        id=org.id,
        display_name=org.display_name,
        currency_code=org.currency_code,
        timezone=org.timezone,
        status=org.status,
    )

    return RequestContext(
        user=current_user,
        organization=org_context,
        membership_id=member.id,
        role=member_role,
    )


def require_permission(permission: Permission) -> Callable[..., RequestContext]:
    """FastAPI dependency factory enforcing an explicit operation permission."""

    async def _require_permission(
        context: RequestContext = Depends(get_request_context),
    ) -> RequestContext:
        context.check_permission(permission)
        return context

    return _require_permission

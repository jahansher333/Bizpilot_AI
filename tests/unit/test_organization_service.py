"""Unit tests for Organization schemas and OrganizationService (ORG-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.core.errors import AuthenticationException, NotFoundException
from app.modules.auth.enums import UserStatus
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.enums import (
    MemberRole,
    MemberStatus,
    OrganizationStatus,
)
from app.modules.organizations.models import Organization, OrganizationMember
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationResponse,
)
from app.modules.organizations.service import OrganizationService


# ==============================================================================
# SCHEMA & VALIDATION TESTS
# ==============================================================================


def test_create_organization_schema_defaults() -> None:
    """Verify default currency PKR and default timezone Asia/Karachi."""
    req = CreateOrganizationRequest(display_name="Al-Rehman Store")
    assert req.display_name == "Al-Rehman Store"
    assert req.currency_code == "PKR"
    assert req.timezone == "Asia/Karachi"


def test_create_organization_display_name_bounds() -> None:
    """Verify display_name min/max length boundaries and whitespace trimming."""
    # Min boundary: 2 chars valid
    req2 = CreateOrganizationRequest(display_name="AB")
    assert req2.display_name == "AB"

    # Too short: 1 char invalid
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="A")

    # Blank / whitespace only invalid
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="   ")

    # Stripping whitespace
    req_ws = CreateOrganizationRequest(display_name="  My Pharmacy  ")
    assert req_ws.display_name == "My Pharmacy"

    # Max boundary: 255 valid
    req_max = CreateOrganizationRequest(display_name="A" * 255)
    assert len(req_max.display_name) == 255

    # Too long: 256 invalid
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="A" * 256)


def test_create_organization_currency_normalization_and_validation() -> None:
    """Verify currency code is normalized to uppercase and validated."""
    req_lower = CreateOrganizationRequest(display_name="Store", currency_code="pkr")
    assert req_lower.currency_code == "PKR"

    # Must be 3 letters
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="Store", currency_code="PK")

    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="Store", currency_code="PK12")

    # Non-ASCII / numbers invalid
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="Store", currency_code="123")


def test_create_organization_timezone_validation() -> None:
    """Verify timezone is validated against IANA zoneinfo database."""
    # Valid timezones
    req_karachi = CreateOrganizationRequest(display_name="Store", timezone="Asia/Karachi")
    assert req_karachi.timezone == "Asia/Karachi"

    req_utc = CreateOrganizationRequest(display_name="Store", timezone="UTC")
    assert req_utc.timezone == "UTC"

    # Invalid timezone rejected
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(display_name="Store", timezone="Invalid/Nonexistent_Timezone")


def test_create_organization_extra_fields_forbidden() -> None:
    """Verify client-supplied owner_id, user_id, role are forbidden."""
    with pytest.raises(ValidationError):
        CreateOrganizationRequest(
            display_name="Store",
            owner_id=str(uuid.uuid4()),  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        CreateOrganizationRequest(
            display_name="Store",
            role="owner",  # type: ignore[call-arg]
        )


# ==============================================================================
# SERVICE UNIT TESTS
# ==============================================================================


@pytest.fixture
def active_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid.uuid4(),
        email_normalized="owner@example.com",
        display_name="Owner User",
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def inactive_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid.uuid4(),
        email_normalized="disabled@example.com",
        display_name="Disabled User",
        status=UserStatus.DISABLED.value,
    )


@pytest.mark.asyncio
async def test_create_organization_atomic_success(active_user: AuthenticatedUser) -> None:
    """Verify OrganizationService creates organization and owner membership atomically."""
    session = AsyncMock()
    repo = AsyncMock(spec=OrganizationRepository)

    now = datetime.now(timezone.utc)
    org_id = uuid.uuid4()
    mock_org = Organization(
        id=org_id,
        display_name="Al-Madina Traders",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status=OrganizationStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )
    mock_member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=active_user.id,
        role=MemberRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        invited_by_user_id=None,
        created_at=now,
        updated_at=now,
    )

    repo.create_organization.return_value = mock_org
    repo.create_member.return_value = mock_member

    service = OrganizationService(session, repository=repo)
    req = CreateOrganizationRequest(display_name="Al-Madina Traders")

    resp = await service.create_organization(active_user, req)

    assert isinstance(resp, OrganizationResponse)
    assert resp.id == str(org_id)
    assert resp.display_name == "Al-Madina Traders"
    assert resp.currency_code == "PKR"
    assert resp.timezone == "Asia/Karachi"
    assert resp.status == "active"
    assert resp.role == "owner"

    repo.create_organization.assert_called_once_with(
        display_name="Al-Madina Traders",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status=OrganizationStatus.ACTIVE.value,
    )
    repo.create_member.assert_called_once_with(
        organization_id=org_id,
        user_id=active_user.id,
        role=MemberRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        invited_by_user_id=None,
    )


@pytest.mark.asyncio
async def test_create_organization_inactive_user_rejected(inactive_user: AuthenticatedUser) -> None:
    """Verify inactive/disabled user cannot create organization."""
    session = AsyncMock()
    repo = AsyncMock(spec=OrganizationRepository)
    service = OrganizationService(session, repository=repo)

    req = CreateOrganizationRequest(display_name="Store")
    with pytest.raises(AuthenticationException) as exc:
        await service.create_organization(inactive_user, req)
    assert exc.value.message == "User account is inactive or disabled"
    repo.create_organization.assert_not_called()


@pytest.mark.asyncio
async def test_get_organization_scoped_success(active_user: AuthenticatedUser) -> None:
    """Verify active member can retrieve organization details."""
    session = AsyncMock()
    repo = AsyncMock(spec=OrganizationRepository)

    now = datetime.now(timezone.utc)
    org_id = uuid.uuid4()
    mock_org = Organization(
        id=org_id,
        display_name="Test Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status=OrganizationStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )
    mock_member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=active_user.id,
        role=MemberRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
        invited_by_user_id=None,
        created_at=now,
        updated_at=now,
    )

    repo.get_organization_with_active_membership.return_value = (mock_org, mock_member)

    service = OrganizationService(session, repository=repo)
    resp = await service.get_organization(active_user, org_id)

    assert resp.id == str(org_id)
    assert resp.role == "owner"
    repo.get_organization_with_active_membership.assert_called_once_with(
        organization_id=org_id,
        user_id=active_user.id,
    )


@pytest.mark.asyncio
async def test_get_organization_non_member_raises_404(active_user: AuthenticatedUser) -> None:
    """Verify non-member receives non-disclosing 404."""
    session = AsyncMock()
    repo = AsyncMock(spec=OrganizationRepository)
    repo.get_organization_with_active_membership.return_value = None

    service = OrganizationService(session, repository=repo)
    with pytest.raises(NotFoundException) as exc:
        await service.get_organization(active_user, uuid.uuid4())
    assert exc.value.message == "Organization not found"


@pytest.mark.asyncio
async def test_list_organizations_returns_active_memberships(active_user: AuthenticatedUser) -> None:
    """Verify listing returns all caller organizations."""
    session = AsyncMock()
    repo = AsyncMock(spec=OrganizationRepository)

    now = datetime.now(timezone.utc)
    org1 = Organization(id=uuid.uuid4(), display_name="Org 1", currency_code="PKR", timezone="Asia/Karachi", status="active", created_at=now, updated_at=now)
    mem1 = OrganizationMember(id=uuid.uuid4(), organization_id=org1.id, user_id=active_user.id, role="owner", status="active", created_at=now, updated_at=now)

    org2 = Organization(id=uuid.uuid4(), display_name="Org 2", currency_code="USD", timezone="UTC", status="active", created_at=now, updated_at=now)
    mem2 = OrganizationMember(id=uuid.uuid4(), organization_id=org2.id, user_id=active_user.id, role="manager", status="active", created_at=now, updated_at=now)

    repo.list_user_organizations_with_active_memberships.return_value = [(org1, mem1), (org2, mem2)]

    service = OrganizationService(session, repository=repo)
    resps = await service.list_organizations(active_user)

    assert len(resps) == 2
    assert resps[0].display_name == "Org 1"
    assert resps[0].role == "owner"
    assert resps[1].display_name == "Org 2"
    assert resps[1].role == "manager"

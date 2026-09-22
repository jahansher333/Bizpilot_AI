"""Unit tests for trusted tenant context and selector extraction (ORG-004)."""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.core.errors import AuthorizationException, ValidationException
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.context import (
    OrganizationContext,
    RequestContext,
    extract_organization_selector,
)
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import (
    Permission,
    get_role_permissions,
)


def _make_dummy_context(role: MemberRole = MemberRole.OWNER) -> RequestContext:
    user = AuthenticatedUser(
        id=uuid.uuid4(),
        email_normalized="owner@example.com",
        display_name="Test Owner",
        status="active",
    )
    org = OrganizationContext(
        id=uuid.uuid4(),
        display_name="Test Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    return RequestContext(
        user=user,
        organization=org,
        membership_id=uuid.uuid4(),
        role=role,
    )


def _make_mock_request(
    path_params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
) -> Request:
    mock_req = MagicMock(spec=Request)
    mock_req.path_params = path_params or {}
    mock_req.headers = Headers(headers or {})
    mock_req.query_params = query_params or {}
    return mock_req


def test_request_context_dataclass_immutability() -> None:
    """RequestContext is an immutable frozen dataclass and cannot be mutated at runtime."""
    ctx = _make_dummy_context(MemberRole.OWNER)

    with pytest.raises((FrozenInstanceError, AttributeError)):
        ctx.role = MemberRole.MANAGER  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        ctx.membership_id = uuid.uuid4()  # type: ignore[misc]


def test_request_context_convenience_properties() -> None:
    """Convenience properties mirror underlying entity IDs."""
    ctx = _make_dummy_context(MemberRole.MANAGER)
    assert ctx.organization_id == ctx.organization.id
    assert ctx.user_id == ctx.user.id


def test_request_context_permissions_derived_from_org003() -> None:
    """Permissions property dynamically derives frozen sets from ORG-003."""
    owner_ctx = _make_dummy_context(MemberRole.OWNER)
    assert owner_ctx.permissions == get_role_permissions(MemberRole.OWNER)
    assert len(owner_ctx.permissions) == 39

    manager_ctx = _make_dummy_context(MemberRole.MANAGER)
    assert manager_ctx.permissions == get_role_permissions(MemberRole.MANAGER)
    assert len(manager_ctx.permissions) == 28

    staff_ctx = _make_dummy_context(MemberRole.STAFF)
    assert staff_ctx.permissions == get_role_permissions(MemberRole.STAFF)
    assert len(staff_ctx.permissions) == 11


def test_request_context_has_permission_checks() -> None:
    """has_permission evaluates positive and negative capabilities matching role matrix."""
    mgr_ctx = _make_dummy_context(MemberRole.MANAGER)
    # Routine corrections allowed
    assert mgr_ctx.has_permission(Permission.ORDERS_CORRECT) is True
    assert mgr_ctx.has_permission(Permission.PAYMENTS_CORRECT) is True
    # Voids denied
    assert mgr_ctx.has_permission(Permission.ORDERS_VOID) is False
    assert mgr_ctx.has_permission(Permission.PAYMENTS_VOID) is False

    staff_ctx = _make_dummy_context(MemberRole.STAFF)
    assert staff_ctx.has_permission(Permission.ORDERS_CREATE) is True
    assert staff_ctx.has_permission(Permission.ORDERS_CORRECT) is False
    assert staff_ctx.has_permission(Permission.ORDERS_VOID) is False


def test_request_context_check_permission_raises_403() -> None:
    """check_permission raises standard 403 AuthorizationException when unauthorized."""
    mgr_ctx = _make_dummy_context(MemberRole.MANAGER)
    # Allowed does not raise
    mgr_ctx.check_permission(Permission.ORDERS_CORRECT)

    # Denied raises AuthorizationException
    with pytest.raises(AuthorizationException) as exc_info:
        mgr_ctx.check_permission(Permission.ORDERS_VOID)
    assert exc_info.value.status_code == 403


def test_selector_extraction_path_parameter() -> None:
    """Selector resolves from path parameter when present."""
    expected_id = uuid.uuid4()
    req = _make_mock_request(path_params={"organization_id": str(expected_id)})
    resolved = extract_organization_selector(req)
    assert resolved == expected_id


def test_selector_extraction_header_fallback() -> None:
    """Selector resolves from X-Organization-ID header when path parameter is absent."""
    expected_id = uuid.uuid4()
    req = _make_mock_request(headers={"X-Organization-ID": str(expected_id)})
    resolved = extract_organization_selector(req)
    assert resolved == expected_id


def test_selector_path_precedence_over_header() -> None:
    """Founder Decision 1: When both path and header exist, PATH WINS without reconciliation."""
    path_id = uuid.uuid4()
    header_id = uuid.uuid4()
    assert path_id != header_id

    req = _make_mock_request(
        path_params={"organization_id": str(path_id)},
        headers={"X-Organization-ID": str(header_id)},
    )
    resolved = extract_organization_selector(req)
    assert resolved == path_id


def test_selector_missing_raises_validation_exception() -> None:
    """Missing selector raises 422 ValidationException."""
    req = _make_mock_request()
    with pytest.raises(ValidationException) as exc_info:
        extract_organization_selector(req)
    assert exc_info.value.status_code == 422
    assert "Organization context required" in exc_info.value.message


def test_selector_malformed_uuid_raises_validation_exception() -> None:
    """Malformed UUID selector raises 422 ValidationException."""
    req = _make_mock_request(path_params={"organization_id": "not-a-valid-uuid"})
    with pytest.raises(ValidationException) as exc_info:
        extract_organization_selector(req)
    assert exc_info.value.status_code == 422
    assert "Invalid organization selector format" in exc_info.value.message


def test_selector_ignores_query_params() -> None:
    """Query parameter ?organization_id= is ignored and does not satisfy required context."""
    req = _make_mock_request(query_params={"organization_id": str(uuid.uuid4())})
    with pytest.raises(ValidationException) as exc_info:
        extract_organization_selector(req)
    assert exc_info.value.status_code == 422

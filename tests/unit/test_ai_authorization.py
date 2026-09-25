"""Unit tests for AI Tool Authorization Wrapper (AI-003)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.ai.authorization import AIToolAuthorizationWrapper, TOOL_PERMISSIONS
from app.modules.ai.schemas import ToolErrorCode
from app.modules.auth.tokens import AuthenticatedUser
from app.modules.organizations.context import OrganizationContext, RequestContext
from app.modules.organizations.enums import MemberRole, OrganizationStatus


def make_context(role: MemberRole, org_id: str | None = None) -> RequestContext:
    active_org_id = uuid4() if org_id is None else org_id
    user = AuthenticatedUser(
        id=uuid4(),
        email_normalized="test@bizpilot.test",
        display_name="Test User",
        status="active",
    )
    org = OrganizationContext(
        id=active_org_id,
        display_name="Test Enterprise",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status=OrganizationStatus.ACTIVE.value,
    )
    return RequestContext(
        user=user,
        organization=org,
        membership_id=uuid4(),
        role=role,
    )


def test_owner_permitted_for_all_approved_tools() -> None:
    ctx = make_context(MemberRole.OWNER)
    for tool_name in TOOL_PERMISSIONS:
        authorized, error = AIToolAuthorizationWrapper.check_tool_authorization(ctx, tool_name)
        assert authorized is True
        assert error is None


def test_manager_permitted_for_all_approved_tools() -> None:
    ctx = make_context(MemberRole.MANAGER)
    for tool_name in TOOL_PERMISSIONS:
        authorized, error = AIToolAuthorizationWrapper.check_tool_authorization(ctx, tool_name)
        assert authorized is True
        assert error is None


def test_staff_permitted_for_operational_tools() -> None:
    ctx = make_context(MemberRole.STAFF)
    operational_tools = [
        "get_sales_summary",
        "get_inventory_status",
        "get_customer_balance",
        "get_order_details",
        "get_top_products",
        "get_payment_summary",
        "get_dashboard_summary",
    ]
    for tool_name in operational_tools:
        authorized, error = AIToolAuthorizationWrapper.check_tool_authorization(ctx, tool_name)
        assert authorized is True
        assert error is None


def test_staff_strictly_denied_for_expense_summary() -> None:
    ctx = make_context(MemberRole.STAFF)
    authorized, error = AIToolAuthorizationWrapper.check_tool_authorization(
        ctx, "get_expense_summary"
    )
    assert authorized is False
    assert error is not None
    assert error.code == ToolErrorCode.AUTHORIZATION_DENIED
    assert "expenses:read" in error.details["required_permission"]
    assert "staff" in error.details["role"]


def test_unknown_unapproved_tool_rejected() -> None:
    ctx = make_context(MemberRole.OWNER)
    authorized, error = AIToolAuthorizationWrapper.check_tool_authorization(
        ctx, "execute_arbitrary_sql"
    )
    assert authorized is False
    assert error is not None
    assert error.code == ToolErrorCode.VALIDATION_ERROR
    assert "not an approved" in error.message


def test_prompt_injection_tenant_override_is_neutralized() -> None:
    trusted_org_id = uuid4()
    ctx = make_context(MemberRole.OWNER, org_id=trusted_org_id)

    attacker_org_id = uuid4()
    malicious_model_args = {
        "organization_id": str(attacker_org_id),
        "tenant_id": str(attacker_org_id),
        "org_id": str(attacker_org_id),
        "period": "today",
    }

    sanitized = AIToolAuthorizationWrapper.sanitize_and_bind_arguments(ctx, malicious_model_args)

    # Attacker's organization IDs are completely stripped and replaced with trusted ID
    assert sanitized["organization_id"] == trusted_org_id
    assert sanitized.get("tenant_id") is None
    assert sanitized.get("org_id") is None
    assert sanitized["period"] == "today"


def test_empty_arguments_safely_binds_trusted_org() -> None:
    trusted_org_id = uuid4()
    ctx = make_context(MemberRole.OWNER, org_id=trusted_org_id)

    sanitized = AIToolAuthorizationWrapper.sanitize_and_bind_arguments(ctx, None)
    assert sanitized["organization_id"] == trusted_org_id

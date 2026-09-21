"""Unit tests for testing foundation, fixtures, and tenant context helpers."""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import ErrorCode
from tests.helpers import (
    RoleEnum,
    TwoOrganizationContext,
    assert_cross_tenant_denial,
)


def test_two_organization_context_isolation(two_org_context: TwoOrganizationContext) -> None:
    alpha = two_org_context.org_alpha
    beta = two_org_context.org_beta

    # Verify organizations have distinct identities
    assert alpha.organization_id != beta.organization_id
    assert alpha.name != beta.name

    # Verify members within Org Alpha have distinct identities
    assert alpha.owner.user_id != alpha.manager.user_id
    assert alpha.owner.user_id != alpha.staff.user_id
    assert alpha.manager.user_id != alpha.staff.user_id

    # Verify members within Org Beta have distinct identities
    assert beta.owner.user_id != beta.manager.user_id
    assert beta.owner.user_id != beta.staff.user_id
    assert beta.manager.user_id != beta.staff.user_id

    # Verify cross-org user separation
    all_user_ids = {
        alpha.owner.user_id,
        alpha.manager.user_id,
        alpha.staff.user_id,
        beta.owner.user_id,
        beta.manager.user_id,
        beta.staff.user_id,
    }
    assert len(all_user_ids) == 6

    # Verify roles
    assert alpha.owner.role == RoleEnum.OWNER
    assert alpha.manager.role == RoleEnum.MANAGER
    assert alpha.staff.role == RoleEnum.STAFF

    # Verify request context generation
    ctx = alpha.owner.request_context
    assert ctx.user_id == alpha.owner.user_id
    assert ctx.organization_id == alpha.organization_id


def test_assert_cross_tenant_denial_helper() -> None:
    # Simulating a safe 404 non-disclosing error response
    response_404 = httpx.Response(
        status_code=404,
        json={
            "error": {
                "code": ErrorCode.RESOURCE_NOT_FOUND.value,
                "message": "Resource not found",
            }
        },
    )
    # Should pass without raising
    assert_cross_tenant_denial(response_404)

    # Simulating a safe 403 forbidden error response
    response_403 = httpx.Response(
        status_code=403,
        json={
            "error": {
                "code": ErrorCode.PERMISSION_DENIED.value,
                "message": "Permission denied",
            }
        },
    )
    # Should pass without raising
    assert_cross_tenant_denial(response_403)

    # Simulating an unsafe 200 response
    response_200 = httpx.Response(
        status_code=200,
        json={"data": "leaked cross-tenant data"},
    )
    with pytest.raises(AssertionError):
        assert_cross_tenant_denial(response_200)

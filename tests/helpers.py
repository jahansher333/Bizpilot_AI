"""Testing helpers and tenant context definitions for BizPilot AI tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx
from fastapi import FastAPI, Response, status
from fastapi.testclient import TestClient

from app.core.dependencies import RequestContext
from app.core.errors import ErrorCode


class RoleEnum(StrEnum):
    __test__ = False
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


TenantRole = RoleEnum


@dataclass(frozen=True)
class TenantActor:
    __test__ = False
    """Represents an authenticated user within an organization context."""

    user_id: str
    organization_id: str
    role: RoleEnum
    email: str

    @property
    def request_context(self) -> RequestContext:
        return RequestContext(user_id=self.user_id, organization_id=self.organization_id)

    @property
    def headers(self) -> dict[str, str]:
        # Foundation mock authentication headers for testing context injection
        return {
            "x-test-user-id": self.user_id,
            "x-test-organization-id": self.organization_id,
            "x-test-role": self.role.value,
        }


@dataclass(frozen=True)
class OrganizationFixtureContext:
    """Represents an organization with its distinct member actors."""

    organization_id: str
    name: str
    owner: TenantActor
    manager: TenantActor
    staff: TenantActor


@dataclass(frozen=True)
class TwoOrganizationContext:
    """Standard two-organization test fixture for verifying multi-tenancy and IDOR."""

    org_alpha: OrganizationFixtureContext
    org_beta: OrganizationFixtureContext


def build_two_organization_context() -> TwoOrganizationContext:
    """Construct deterministic two-organization test contexts with distinct IDs."""
    alpha_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "alpha.bizpilot.test"))
    beta_org_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "beta.bizpilot.test"))

    org_alpha = OrganizationFixtureContext(
        organization_id=alpha_org_id,
        name="Alpha Traders",
        owner=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "owner@alpha.bizpilot.test")),
            organization_id=alpha_org_id,
            role=RoleEnum.OWNER,
            email="owner@alpha.bizpilot.test",
        ),
        manager=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "manager@alpha.bizpilot.test")),
            organization_id=alpha_org_id,
            role=RoleEnum.MANAGER,
            email="manager@alpha.bizpilot.test",
        ),
        staff=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "staff@alpha.bizpilot.test")),
            organization_id=alpha_org_id,
            role=RoleEnum.STAFF,
            email="staff@alpha.bizpilot.test",
        ),
    )

    org_beta = OrganizationFixtureContext(
        organization_id=beta_org_id,
        name="Beta Logistics",
        owner=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "owner@beta.bizpilot.test")),
            organization_id=beta_org_id,
            role=RoleEnum.OWNER,
            email="owner@beta.bizpilot.test",
        ),
        manager=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "manager@beta.bizpilot.test")),
            organization_id=beta_org_id,
            role=RoleEnum.MANAGER,
            email="manager@beta.bizpilot.test",
        ),
        staff=TenantActor(
            user_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "staff@beta.bizpilot.test")),
            organization_id=beta_org_id,
            role=RoleEnum.STAFF,
            email="staff@beta.bizpilot.test",
        ),
    )

    return TwoOrganizationContext(org_alpha=org_alpha, org_beta=org_beta)


def assert_cross_tenant_denial(
    response: httpx.Response,
    allowed_codes: tuple[int, ...] = (
        status.HTTP_404_NOT_FOUND,
        status.HTTP_403_FORBIDDEN,
    ),
) -> None:
    """Assert that a cross-tenant access attempt was rejected safely without disclosure."""
    assert response.status_code in allowed_codes, (
        f"Cross-tenant access must be denied with {allowed_codes}, got status {response.status_code}"
    )
    # Ensure no data leak in error response
    data = response.json()
    assert "error" in data, "Error response must follow standard error contract"
    assert data["error"]["code"] in {
        ErrorCode.RESOURCE_NOT_FOUND.value,
        ErrorCode.PERMISSION_DENIED.value,
    }

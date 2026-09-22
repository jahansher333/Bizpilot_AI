"""Security and adversarial tests for internal trace foundation (ORG-006)."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationException
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import (
    Permission,
    get_role_permissions,
    has_permission,
)
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.models import InternalTraceEvent
from app.modules.trace.repository import InternalTraceRepository
from app.modules.trace.sanitizer import (
    MAX_METADATA_BYTES,
    REDACTED_VALUE,
    sanitize_and_validate_metadata,
)
from app.modules.trace.service import InternalTraceService
from tests.integration.test_internal_trace_integration import _create_test_org


def test_permission_separation_trace_read_internal() -> None:
    """Verify trace:read_internal is exclusively granted to Owner role."""
    assert Permission.TRACE_READ_INTERNAL.value == "trace:read_internal"

    # Owner has TRACE_READ_INTERNAL
    assert has_permission(MemberRole.OWNER, Permission.TRACE_READ_INTERNAL)

    # Manager and Staff do NOT have TRACE_READ_INTERNAL
    assert not has_permission(MemberRole.MANAGER, Permission.TRACE_READ_INTERNAL)
    assert not has_permission(MemberRole.STAFF, Permission.TRACE_READ_INTERNAL)

    manager_perms = get_role_permissions(MemberRole.MANAGER)
    assert Permission.TRACE_READ_INTERNAL not in manager_perms

    staff_perms = get_role_permissions(MemberRole.STAFF)
    assert Permission.TRACE_READ_INTERNAL not in staff_perms


def test_adversarial_metadata_credential_leakage() -> None:
    """Adversarial test: Inject various credential formats, casing, and separators."""
    adversarial_payload = {
        "User_Password": "leak_password_123",
        "access_token": "eyJhbGciOi...",
        "REFRESH-TOKEN": "sensitive_refresh_val",
        "api-key": "sk-live-9999",
        "AuthHeader": "Bearer super-secret-token",
        "nested": {
            "cvv": "999",
            "card_number": "4111-2222-3333-4444",
            "bank_account": "PK360000",
            "iban": "PK36MEZN123456789",
            "jwt": "token_val",
            "secret": "top-secret",
            "cookie": "session=secret",
            "deep": {
                "raw_prompt": "Confidential financial data dump",
                "system_prompt": "System internal instruction",
                "completion": "Generated confidential text",
                "embedding": [0.123, 0.456],
                "request_body": "{\"password\": \"secret\"}",
                "response_body": "{\"token\": \"secret\"}",
            },
        },
        "safe_reference": "inv_12345",
    }

    sanitized = sanitize_and_validate_metadata(adversarial_payload)

    assert sanitized["User_Password"] == REDACTED_VALUE
    assert sanitized["access_token"] == REDACTED_VALUE
    assert sanitized["REFRESH-TOKEN"] == REDACTED_VALUE
    assert sanitized["api-key"] == REDACTED_VALUE
    assert sanitized["AuthHeader"] == REDACTED_VALUE
    assert sanitized["nested"]["cvv"] == REDACTED_VALUE
    assert sanitized["nested"]["card_number"] == REDACTED_VALUE
    assert sanitized["nested"]["bank_account"] == REDACTED_VALUE
    assert sanitized["nested"]["iban"] == REDACTED_VALUE
    assert sanitized["nested"]["jwt"] == REDACTED_VALUE
    assert sanitized["nested"]["secret"] == REDACTED_VALUE
    assert sanitized["nested"]["cookie"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["raw_prompt"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["system_prompt"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["completion"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["embedding"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["request_body"] == REDACTED_VALUE
    assert sanitized["nested"]["deep"]["response_body"] == REDACTED_VALUE
    assert sanitized["safe_reference"] == "inv_12345"


def test_adversarial_unserializable_class_repr_leakage() -> None:
    """Adversarial test: Ensure objects whose repr or str contains secrets are safely sanitized."""
    class MaliciousExploit:
        def __str__(self) -> str:
            return "SECRET_ADMIN_TOKEN_LEAK"

        def __repr__(self) -> str:
            return "DATABASE_CONNECTION_STRING_LEAK"

    payload = {"exploit": MaliciousExploit()}
    sanitized = sanitize_and_validate_metadata(payload)
    assert sanitized["exploit"] == "<unserializable>"
    assert "SECRET_ADMIN_TOKEN_LEAK" not in str(sanitized)
    assert "DATABASE_CONNECTION_STRING_LEAK" not in str(sanitized)


def test_oversized_metadata_does_not_leak_payload_in_exception() -> None:
    """Adversarial test: Ensure oversized payload rejection does not reflect sensitive contents."""
    sensitive_secret = "VERY_CONFIDENTIAL_TOKEN_SECRET_12345"
    oversized = {"data": sensitive_secret + ("a" * 5000)}

    with pytest.raises(ValidationException) as exc_info:
        sanitize_and_validate_metadata(oversized)

    error_msg = str(exc_info.value)
    assert f"Trace metadata exceeds maximum size limit of {MAX_METADATA_BYTES} bytes" in error_msg
    assert sensitive_secret not in error_msg


@pytest.mark.asyncio
async def test_cross_tenant_trace_idor_isolation(db_session: AsyncSession) -> None:
    """Adversarial test: Tenant B cannot read or discover Tenant A's trace events."""
    org_a = await _create_test_org(db_session, "Security Org A")
    org_b = await _create_test_org(db_session, "Security Org B")

    service_a = InternalTraceService(session=db_session, organization_id=org_a.id)
    event_a = await service_a.record_event(
        action=TraceAction.SECURITY_ACCESS_DENIED,
        outcome=TraceOutcome.DENIED,
        metadata={"ip": "10.0.0.1"},
    )

    # Repository for Org B attempts to look up event_a.id
    repo_b = InternalTraceRepository(session=db_session, organization_id=org_b.id)
    retrieved = await repo_b.get_event_by_id(event_a.id)
    assert retrieved is None

    # Listing events for Org B returns empty list
    events_b = await repo_b.list_events()
    assert len(events_b) == 0


@pytest.mark.asyncio
async def test_repository_rejects_foreign_tenant_event_injection(db_session: AsyncSession) -> None:
    """Adversarial test: Repository refuses to stage an event with mismatched organization_id."""
    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()

    repo_b = InternalTraceRepository(session=db_session, organization_id=org_b_id)

    # Malicious attempt to inject an event created under Org A into Org B's repository
    event_forged = InternalTraceEvent(
        id=uuid.uuid4(),
        organization_id=org_a_id,  # Mismatched!
        action="org.member.invited",
        outcome="success",
        event_metadata={},
    )

    with pytest.raises(ValueError) as exc_info:
        repo_b.add_event(event_forged)

    assert "does not match repository organization_id" in str(exc_info.value)


@pytest.mark.asyncio
async def test_service_trusts_only_bound_organization_id(db_session: AsyncSession) -> None:
    """Adversarial test: Untrusted tenant selectors in metadata do not alter event.organization_id."""
    org = await _create_test_org(db_session, "Trusted Org")
    forged_org_id = uuid.uuid4()

    service = InternalTraceService(session=db_session, organization_id=org.id)

    # Attacker tries to pass forged organization_id or actor_user_id in metadata
    event = await service.record_event(
        action=TraceAction.SECURITY_ACCESS_DENIED,
        outcome=TraceOutcome.DENIED,
        metadata={
            "organization_id": str(forged_org_id),
            "tenant_id": str(forged_org_id),
            "role": "owner",
        },
    )

    # The actual persisted event organization_id is strictly the trusted org.id
    assert event.organization_id == org.id
    assert event.organization_id != forged_org_id


def test_append_only_contract_immutability_guarantees() -> None:
    """Verify that InternalTraceRepository and InternalTraceEvent enforce append-only invariants."""
    # 1. Model has no updated_at column
    assert not hasattr(InternalTraceEvent, "updated_at")

    # 2. Repository provides no mutation or deletion APIs
    org_id = uuid.uuid4()
    repo = InternalTraceRepository(session=None, organization_id=org_id)  # type: ignore[arg-type]

    forbidden_methods = [
        "update",
        "delete",
        "bulk_update",
        "bulk_delete",
        "rebind_organization",
        "set_organization_id",
    ]
    for method in forbidden_methods:
        assert not hasattr(repo, method), f"Forbidden method {method} exists on InternalTraceRepository"

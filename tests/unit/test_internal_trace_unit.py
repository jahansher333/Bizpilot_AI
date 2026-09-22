"""Unit tests for internal trace contracts, sanitization, and repositories (ORG-006)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import pytest

from app.core.errors import ValidationException
from app.db.repositories import TenantScopedModel, validate_tenant_model
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.models import InternalTraceEvent
from app.modules.trace.repository import InternalTraceRepository
from app.modules.trace.sanitizer import (
    MAX_METADATA_BYTES,
    REDACTED_VALUE,
    is_sensitive_key,
    sanitize_and_validate_metadata,
)


def test_trace_outcome_enum_values() -> None:
    """Verify TraceOutcome contains only approved deterministic outcomes."""
    assert TraceOutcome.SUCCESS.value == "success"
    assert TraceOutcome.DENIED.value == "denied"
    assert TraceOutcome.FAILED.value == "failed"
    assert len(TraceOutcome) == 3


def test_trace_action_naming_and_registry() -> None:
    """Verify TraceAction entries conform to lowercase namespaced dot notation."""
    for action in TraceAction:
        val = action.value
        assert val == val.lower(), f"Action {val} is not lowercase"
        assert "." in val, f"Action {val} is not dot-namespaced"
        assert len(val) >= 3, f"Action {val} is too short"
        assert len(val) <= 64, f"Action {val} exceeds 64 characters"

    assert TraceAction.ORG_MEMBER_INVITED == "org.member.invited"
    assert TraceAction.ORG_MEMBER_REVOKED == "org.member.revoked"
    assert TraceAction.ORG_MEMBER_ROLE_CHANGED == "org.member.role_changed"
    assert TraceAction.ORG_STATUS_CHANGED == "org.status.changed"
    assert TraceAction.SECURITY_ACCESS_DENIED == "security.access.denied"
    assert TraceAction.FINANCE_RECORD_VOIDED == "finance.record.voided"
    assert TraceAction.FINANCE_RECORD_CORRECTED == "finance.record.corrected"


def test_internal_trace_event_satisfies_tenant_scoped_model() -> None:
    """Verify InternalTraceEvent model satisfies the TenantScopedModel contract."""
    validate_tenant_model(InternalTraceEvent)
    assert hasattr(InternalTraceEvent, "id")
    assert hasattr(InternalTraceEvent, "organization_id")
    # Verify absence of updated_at column per append-only specification
    assert not hasattr(InternalTraceEvent, "updated_at")


def test_metadata_sanitizer_redacts_credentials_and_tokens() -> None:
    """Verify all credential, token, and key fields are replaced with [REDACTED]."""
    raw = {
        "password": "super-secret-password",
        "password_hash": "$2b$12$e80k...",
        "new_password": "new-secret-value",
        "old_password": "old-secret-value",
        "token": "raw-token-value",
        "access_token": "jwt.token.string",
        "refresh_token": "refresh-token-data",
        "reset_token": "reset-token-data",
        "jwt": "eyJhbGciOi...",
        "secret": "my-secret-key",
        "api_key": "live_sk_12345",
        "authorization": "Bearer token123",
        "cookie": "sessionid=xyz",
        "set_cookie": "token=abc",
        "cvv": "123",
        "card_number": "4111222233334444",
        "credit_card": "4111222233334444",
        "bank_account": "PK36MEZN0001234567890101",
        "iban": "PK36MEZN0001234567890101",
        "safe_reason": "quota_exceeded",
        "count": 42,
    }
    sanitized = sanitize_and_validate_metadata(raw)

    for k, v in sanitized.items():
        if k in ("safe_reason", "count"):
            continue
        assert v == REDACTED_VALUE, f"Key {k} was not redacted, got: {v}"

    assert sanitized["safe_reason"] == "quota_exceeded"
    assert sanitized["count"] == 42


def test_metadata_sanitizer_case_and_separator_variants() -> None:
    """Verify camelCase, UPPERCASE, kebab-case, and mixed separators are redacted."""
    raw = {
        "accessToken": "secret-token-1",
        "ACCESS_TOKEN": "secret-token-2",
        "refresh-token": "secret-token-3",
        "authorization_header": "Bearer abc",
        "PasswordHash": "hash123",
        "API-KEY": "api-key-val",
        "authSecret": "auth-secret-val",
        "CreditCard": "4111-2222-3333-4444",
        "BankAccount": "account-123",
    }
    sanitized = sanitize_and_validate_metadata(raw)

    for k, v in sanitized.items():
        assert v == REDACTED_VALUE, f"Variant key {k} was not redacted, got: {v}"


def test_metadata_sanitizer_recursively_handles_nested_structures() -> None:
    """Verify nested dictionaries, lists, and tuples are sanitized at all depths."""
    raw = {
        "user_info": {
            "name": "Ali",
            "account_details": {
                "password": "nested-password",
                "api_key": "nested-api-key",
            },
            "credentials": "top-level-credential",
        },
        "sessions": [
            {"token": "token-in-list", "active": True},
            {"ip": "127.0.0.1", "secret": "secret-in-list"},
        ],
    }
    sanitized = sanitize_and_validate_metadata(raw)

    assert sanitized["user_info"]["name"] == "Ali"
    assert sanitized["user_info"]["credentials"] == REDACTED_VALUE
    assert sanitized["user_info"]["account_details"]["password"] == REDACTED_VALUE
    assert sanitized["user_info"]["account_details"]["api_key"] == REDACTED_VALUE
    assert sanitized["sessions"][0]["token"] == REDACTED_VALUE
    assert sanitized["sessions"][0]["active"] is True
    assert sanitized["sessions"][1]["secret"] == REDACTED_VALUE
    assert sanitized["sessions"][1]["ip"] == "127.0.0.1"


def test_metadata_sanitizer_redacts_ai_and_payload_keys() -> None:
    """Verify raw AI prompts, completions, and HTTP request/response bodies are redacted."""
    raw = {
        "prompt": "Tell me the secret financials",
        "raw_prompt": "You are a helpful assistant...",
        "system_prompt": "Confidential instructions...",
        "completion": "The confidential answer is...",
        "embedding": [0.1, 0.2, 0.3],
        "request_body": "{\"user\": \"ali\", \"pin\": \"1234\"}",
        "response_body": "{\"balance\": 500000}",
        "action_context": "invoice_void",
    }
    sanitized = sanitize_and_validate_metadata(raw)

    assert sanitized["prompt"] == REDACTED_VALUE
    assert sanitized["raw_prompt"] == REDACTED_VALUE
    assert sanitized["system_prompt"] == REDACTED_VALUE
    assert sanitized["completion"] == REDACTED_VALUE
    assert sanitized["embedding"] == REDACTED_VALUE
    assert sanitized["request_body"] == REDACTED_VALUE
    assert sanitized["response_body"] == REDACTED_VALUE
    assert sanitized["action_context"] == "invoice_void"


def test_metadata_sanitizer_serializes_safe_primitives() -> None:
    """Verify UUID, datetime, date, Decimal, and Enum serialize correctly to JSON-safe primitives."""
    class SampleEnum(str, Enum):
        VAL = "enum_value"

    test_uuid = uuid.uuid4()
    test_dt = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    test_dec = Decimal("12500.50")

    raw = {
        "id": test_uuid,
        "timestamp": test_dt,
        "amount": test_dec,
        "mode": SampleEnum.VAL,
    }
    sanitized = sanitize_and_validate_metadata(raw)

    assert sanitized["id"] == str(test_uuid)
    assert sanitized["timestamp"] == test_dt.isoformat()
    assert sanitized["amount"] == "12500.50"
    assert sanitized["mode"] == "enum_value"


def test_metadata_sanitizer_handles_unsupported_objects_safely() -> None:
    """Verify arbitrary custom objects serialize to placeholder without invoking repr or leaking data."""
    class CustomObj:
        def __repr__(self) -> str:
            raise RuntimeError("Should never call repr")

        def __str__(self) -> str:
            return "LEAKED_STRING_REPR"

    raw = {"obj": CustomObj()}
    sanitized = sanitize_and_validate_metadata(raw)
    assert sanitized["obj"] == "<unserializable>"


def test_metadata_size_limit_accepted_under_boundary() -> None:
    """Verify metadata under or equal to 4096 bytes serialized is accepted."""
    small_payload = {"key": "value" * 10}
    sanitized = sanitize_and_validate_metadata(small_payload)
    assert sanitized["key"] == "value" * 10


def test_metadata_size_limit_rejected_over_boundary() -> None:
    """Verify metadata exceeding 4096 bytes serialized is rejected with safe ValidationException."""
    large_payload = {"key": "x" * 5000}
    with pytest.raises(ValidationException) as exc_info:
        sanitize_and_validate_metadata(large_payload)

    # Verify no payload content is leaked in the exception message
    msg = str(exc_info.value)
    assert "Trace metadata exceeds maximum size limit of 4096 bytes" in msg
    assert "xxxxx" not in msg


def test_metadata_size_measures_utf8_bytes_not_characters() -> None:
    """Verify multi-byte Unicode characters (e.g. Urdu/emoji) are measured in UTF-8 bytes."""
    # Urdu text: 2 bytes per char in UTF-8
    # 2500 chars (5 * 500) < 4096 characters, but UTF-8 bytes = 5000 bytes > 4096 bytes
    urdu_text = "\u062a\u062c\u0627\u0631\u062a" * 500
    assert len(urdu_text) == 2500  # Character count is well under 4096
    assert len(urdu_text.encode("utf-8")) == 5000  # UTF-8 byte count exceeds 4096

    with pytest.raises(ValidationException) as exc_info:
        sanitize_and_validate_metadata({"urdu": urdu_text})
    assert "exceeds maximum size limit" in str(exc_info.value)


def test_metadata_sanitizer_none_and_invalid_type() -> None:
    """Verify None produces empty dict and non-dict raises ValidationException."""
    assert sanitize_and_validate_metadata(None) == {}
    with pytest.raises(ValidationException) as exc:
        sanitize_and_validate_metadata("not-a-dict")  # type: ignore[arg-type]
    assert "Trace metadata must be a dictionary" in str(exc.value)


def test_repository_organization_id_immutability() -> None:
    """Verify organization_id is immutable on InternalTraceRepository."""
    org_id = uuid.uuid4()
    repo = InternalTraceRepository(session=None, organization_id=org_id)  # type: ignore[arg-type]

    assert repo.organization_id == org_id
    with pytest.raises(AttributeError):
        repo.organization_id = uuid.uuid4()  # type: ignore[misc]

    with pytest.raises(AttributeError):
        repo._organization_id = uuid.uuid4()


def test_repository_exposes_no_mutation_or_deletion_apis() -> None:
    """Verify InternalTraceRepository adheres strictly to append-only contract."""
    org_id = uuid.uuid4()
    repo = InternalTraceRepository(session=None, organization_id=org_id)  # type: ignore[arg-type]

    assert not hasattr(repo, "update")
    assert not hasattr(repo, "delete")
    assert not hasattr(repo, "bulk_update")
    assert not hasattr(repo, "bulk_delete")
    assert hasattr(repo, "add_event")
    assert hasattr(repo, "get_event_by_id")
    assert hasattr(repo, "list_events")

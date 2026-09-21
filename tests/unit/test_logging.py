"""Unit tests for logging, correlation, and redaction."""

from __future__ import annotations

import json
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonLogFormatter, redact_sensitive_data
from app.core.middleware import CORRELATION_HEADER, CorrelationMiddleware


def test_redact_sensitive_keys() -> None:
    data = {
        "user_id": "usr_123",
        "email": "user@example.com",
        "password": "SuperSecretPassword123!",
        "token": "raw-token-value",
        "auth": {
            "access_token": "bearer-token-val",
            "signing_secret": "signing-key-value",
            "nested_safe": "visible-value",
        },
        "api_key": "sk-12345",
        "database_url": "postgresql://user:pass@localhost:5432/mock_db",
        "items": [
            {"name": "item1", "secret_code": "code123"},
            {"name": "item2", "visible": True},
        ],
    }

    redacted = redact_sensitive_data(data)

    assert redacted["user_id"] == "usr_123"
    assert redacted["email"] == "user@example.com"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["auth"]["access_token"] == "[REDACTED]"
    assert redacted["auth"]["signing_secret"] == "[REDACTED]"
    assert redacted["auth"]["nested_safe"] == "visible-value"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["database_url"] == "[REDACTED]"
    assert redacted["items"][0]["secret_code"] == "[REDACTED]"
    assert redacted["items"][1]["visible"] is True


def test_redact_bearer_token_in_string() -> None:
    text = "Authorization header was Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token.signature in request"
    redacted = redact_sensitive_data(text)
    assert "[REDACTED]" in redacted
    assert "Bearer [REDACTED]" in redacted
    assert "eyJhbGci" not in redacted


def test_correlation_id_generated_when_missing() -> None:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/probe")
    def probe():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/probe")
    assert response.status_code == 200
    corr_id = response.headers.get(CORRELATION_HEADER)
    assert corr_id is not None
    # Validate it's a valid UUID
    parsed = uuid.UUID(corr_id)
    assert str(parsed) == corr_id


def test_correlation_id_propagated_when_provided() -> None:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/probe")
    def probe():
        return {"status": "ok"}

    client = TestClient(app)
    custom_id = "test-client-correlation-uuid-999"
    response = client.get("/probe", headers={CORRELATION_HEADER: custom_id})
    assert response.status_code == 200
    assert response.headers.get(CORRELATION_HEADER) == custom_id


def test_json_log_formatter() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message with %s",
        args=("parameter",),
        exc_info=None,
    )
    record.correlation_id = "test-corr-id-123"
    record.extra_fields = {"password": "should_be_redacted", "safe_field": 42}

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test log message with parameter"
    assert parsed["correlation_id"] == "test-corr-id-123"
    assert parsed["password"] == "[REDACTED]"
    assert parsed["safe_field"] == 42
    assert "timestamp" in parsed

"""Unit tests for error contract and exception handlers."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import (
    AppException,
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    ErrorCode,
    NotFoundException,
    RateLimitException,
    ServiceUnavailableException,
    ValidationException,
    register_error_handlers,
)
from app.core.middleware import CorrelationMiddleware


class SampleBodyModel(BaseModel):
    count: int
    name: str


@pytest.fixture
def error_test_app(test_settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    register_error_handlers(app)

    router = APIRouter()

    @router.get("/trigger-validation")
    def trigger_validation():
        raise ValidationException(message="Custom validation failure")

    @router.get("/trigger-auth")
    def trigger_auth():
        raise AuthenticationException("Login required")

    @router.get("/trigger-forbidden")
    def trigger_forbidden():
        raise AuthorizationException("Access denied to resource")

    @router.get("/trigger-not-found")
    def trigger_not_found():
        raise NotFoundException("Customer not found")

    @router.get("/trigger-conflict")
    def trigger_conflict():
        raise ConflictException("Duplicate reference exists")

    @router.get("/trigger-rate-limit")
    def trigger_rate_limit():
        raise RateLimitException("Rate limit exceeded")

    @router.get("/trigger-unavailable")
    def trigger_unavailable():
        raise ServiceUnavailableException("Database down")

    @router.get("/trigger-unhandled")
    def trigger_unhandled():
        raise RuntimeError("Secret internal database password failure: pass123")

    @router.post("/trigger-pydantic")
    def trigger_pydantic(payload: SampleBodyModel):
        return {"received": payload.name}

    app.include_router(router)
    return app


def test_validation_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-validation")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert body["error"]["message"] == "Custom validation failure"
    assert "correlation_id" in body["error"]
    assert response.headers.get("X-Correlation-ID") == body["error"]["correlation_id"]


def test_authentication_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-auth")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == ErrorCode.AUTHENTICATION_REQUIRED.value
    assert body["error"]["message"] == "Login required"


def test_authorization_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-forbidden")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == ErrorCode.PERMISSION_DENIED.value
    assert body["error"]["message"] == "Access denied to resource"


def test_not_found_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-not-found")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND.value
    assert body["error"]["message"] == "Customer not found"


def test_conflict_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-conflict")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == ErrorCode.CONFLICT.value
    assert body["error"]["message"] == "Duplicate reference exists"


def test_rate_limit_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-rate-limit")
    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == ErrorCode.RATE_LIMITED.value
    assert body["error"]["message"] == "Rate limit exceeded"


def test_service_unavailable_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    response = client.get("/trigger-unavailable")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == ErrorCode.SERVICE_UNAVAILABLE.value
    assert body["error"]["message"] == "Database down"


def test_pydantic_validation_error_contract(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app)
    # Send invalid body (missing required name and invalid count type)
    response = client.post("/trigger-pydantic", json={"count": "not_a_number"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
    assert body["error"]["message"] == "Request validation failed"
    assert isinstance(body["error"]["details"], list)
    fields = [d["field"] for d in body["error"]["details"]]
    assert "count" in fields
    assert "name" in fields


def test_unhandled_exception_is_sanitized(error_test_app: FastAPI) -> None:
    client = TestClient(error_test_app, raise_server_exceptions=False)
    response = client.get("/trigger-unhandled")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == ErrorCode.INTERNAL_SERVER_ERROR.value
    assert body["error"]["message"] == "An unexpected internal server error occurred"
    # Verify no secret text leaked into response
    assert "pass123" not in response.text
    assert "Secret" not in response.text
    assert "correlation_id" in body["error"]

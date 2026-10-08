"""Production does not serve the interactive API docs or the OpenAPI schema (SEC-P1 F6)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def _settings(environment: str) -> Settings:
    if environment != "production":
        return Settings(
            environment=environment,
            database={"url": "postgresql://user:pw@localhost:5432/bizpilot"},
            auth={"signing_secret": "test-only-signing-secret"},
            ai={"enabled": False},
        )
    return Settings(
        environment="production",
        debug=False,
        cors_origins=["https://app.bizpilot.invalid"],
        database={
            "url": "postgresql://runtime_app:S3cure_Db_Credential_2026_Long@db.invalid:5432/bizpilot?sslmode=verify-full"
        },
        auth={"signing_secret": "secure-runtime-signing-secret-over-32-characters"},
        email={
            "smtp_host": "smtp.mail.invalid",
            "smtp_username": "bizpilot-mailer",
            "smtp_password": "Sm7p_Relay_Credential_2026_Long",
            "from_address": "no-reply@bizpilot.invalid",
            "frontend_base_url": "https://app.bizpilot.invalid",
        },
        ai={"enabled": False},
    )


@pytest.mark.parametrize("path", DOC_PATHS)
def test_production_does_not_serve_api_docs(path: str) -> None:
    with TestClient(create_app(_settings("production"))) as client:
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("environment", ["local", "test", "staging"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_non_production_still_serves_api_docs(environment: str, path: str) -> None:
    with TestClient(create_app(_settings(environment))) as client:
        assert client.get(path).status_code == 200


def test_production_health_probe_still_served() -> None:
    with TestClient(create_app(_settings("production"))) as client:
        assert client.get("/healthz").status_code == 200

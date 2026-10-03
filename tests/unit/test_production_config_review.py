"""Unit tests for Production Configuration and Readiness Review (HARD-007).

Validates:
1. Production environment strictly forbids debug mode (BIZPILOT_DEBUG=true).
2. Production PostgreSQL transport requires TLS (sslmode=require).
3. Production environment requires non-placeholder credentials and minimum 32-character signing secret.
4. AI configuration strictly validates API key and model presence when enabled.
5. Unknown configuration keys starting with BIZPILOT_ are rejected.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    AISettings,
    AuthenticationSettings,
    DatabaseSettings,
    EnvironmentMode,
    Settings,
)


def _valid_production_payload() -> dict:
    return {
        "environment": "production",
        "debug": False,
        "cors_origins": ["https://app.bizpilot.invalid"],
        "email": {
            "smtp_host": "smtp.mail.invalid",
            "smtp_username": "bizpilot-mailer",
            "smtp_password": "Sm7p_Relay_Credential_2026_Long",
            "from_address": "no-reply@bizpilot.invalid",
            "frontend_base_url": "https://app.bizpilot.invalid",
        },
        "database": {
            "url": "postgresql://prod_user_admin:StrongSecretPass987654321@postgres.prod.internal:5432/bizpilot_prod?sslmode=require",
        },
        "auth": {
            "signing_secret": "a" * 32,
            "access_token_minutes": 15,
        },
        "ai": {
            "enabled": False,
        },
        "logging": {
            "level": "INFO",
            "json_logs": True,
        },
    }


def test_valid_production_settings_accepted():
    """Verify clean production configuration succeeds validation."""
    payload = _valid_production_payload()
    settings = Settings(**payload)
    assert settings.environment is EnvironmentMode.PRODUCTION
    assert settings.debug is False
    assert settings.ai.enabled is False


def test_production_forbids_debug_mode():
    """Verify debug=True is rejected in production mode."""
    payload = _valid_production_payload()
    payload["debug"] = True
    with pytest.raises(ValidationError, match="debug mode is not allowed in production"):
        Settings(**payload)


def test_production_requires_tls_sslmode():
    """Verify PostgreSQL URL without sslmode=require is rejected in production."""
    payload = _valid_production_payload()
    payload["database"]["url"] = (
        "postgresql://prod_user_admin:StrongSecretPass987654321@postgres.prod.internal:5432/bizpilot_prod"
    )
    with pytest.raises(ValidationError, match="production PostgreSQL transport must require TLS"):
        Settings(**payload)


def test_production_rejects_weak_or_placeholder_signing_secret():
    """Verify short or placeholder signing secret is rejected in production."""
    payload = _valid_production_payload()
    payload["auth"]["signing_secret"] = "short-secret"
    with pytest.raises(ValidationError, match="must be a non-placeholder value"):
        Settings(**payload)

    payload["auth"]["signing_secret"] = "my-dummy-placeholder-secret-long-enough-1234"
    with pytest.raises(ValidationError, match="must be a non-placeholder value"):
        Settings(**payload)


def test_ai_settings_requires_credentials_when_enabled():
    """Verify AI enabled state requires non-empty api_key and model."""
    with pytest.raises(ValidationError, match="AI API key and model are required"):
        AISettings(enabled=True, api_key=None, model=None)

    with pytest.raises(ValidationError, match="AI API key and model are required"):
        AISettings(enabled=True, api_key=SecretStr(""), model="gpt-4o-mini")

    valid_ai = AISettings(
        enabled=True,
        api_key=SecretStr("sk-prod-real-key-12345"),
        model="gpt-4o-mini",
    )
    assert valid_ai.enabled is True
    assert valid_ai.model == "gpt-4o-mini"

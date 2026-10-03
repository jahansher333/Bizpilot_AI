from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import EnvironmentMode, Settings

PREFIX = "BIZPILOT_"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in list(os.environ):
        if name.startswith(PREFIX):
            monkeypatch.delenv(name, raising=False)


def production_email() -> dict[str, object]:
    return {
        "smtp_host": "smtp.mail.invalid",
        "smtp_username": "bizpilot-mailer",
        "smtp_password": "Sm7p_Relay_Credential_2026_Long",
        "from_address": "no-reply@bizpilot.invalid",
        "frontend_base_url": "https://app.bizpilot.invalid",
    }


def values(mode: str = "local") -> dict[str, object]:
    url = "postgresql://user:db-secret-password@localhost:5432/bizpilot"
    cors_origins = ["http://localhost:3000"]
    email: dict[str, object] = {}
    if mode == "production":
        url = (
            "postgresql://runtime_app:S3cure_Db_Credential_2026_Long"
            "@db.invalid:5432/bizpilot?sslmode=verify-full"
        )
        cors_origins = ["https://app.bizpilot.invalid"]
        email = production_email()
    return {
        "environment": mode,
        "debug": False,
        "cors_origins": cors_origins,
        "email": email,
        "database": {"url": url},
        "auth": {"signing_secret": "secure-runtime-signing-secret-over-32-characters"},
        "ai": {"enabled": False},
        "logging": {"level": "INFO"},
    }


@pytest.mark.parametrize("mode", ["local", "test", "staging", "production"])
def test_valid_modes(mode: str) -> None:
    assert Settings(**values(mode)).environment is EnvironmentMode(mode)


@pytest.mark.parametrize("missing", ["environment", "database", "auth"])
def test_required_settings_fail_when_missing(missing: str) -> None:
    config = values()
    del config[missing]
    with pytest.raises(ValidationError):
        Settings(**config)


def test_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(**(values() | {"environment": "preview"}))


def test_invalid_logging_level() -> None:
    config = values()
    config["logging"] = {"level": "VERBOSE"}
    with pytest.raises(ValidationError):
        Settings(**config)


def test_malformed_postgresql_url() -> None:
    config = values()
    config["database"] = {"url": "mysql://user:password@localhost/db"}
    with pytest.raises(ValidationError):
        Settings(**config)


@pytest.mark.parametrize("secret", ["", "   "])
def test_auth_secret_must_not_be_blank(secret: str) -> None:
    config = values()
    config["auth"] = {"signing_secret": secret}
    with pytest.raises(ValidationError):
        Settings(**config)


def test_ai_enabled_requires_configuration() -> None:
    config = values()
    config["ai"] = {"enabled": True}
    with pytest.raises(ValidationError):
        Settings(**config)


@pytest.mark.parametrize(
    "ai",
    [
        {"enabled": True, "api_key": "", "model": "approved-model"},
        {"enabled": True, "api_key": "   ", "model": "approved-model"},
        {"enabled": True, "api_key": "test-key", "model": ""},
        {"enabled": True, "api_key": "test-key", "model": "   "},
    ],
)
def test_ai_enabled_rejects_blank_configuration(ai: dict[str, object]) -> None:
    config = values()
    config["ai"] = ai
    with pytest.raises(ValidationError):
        Settings(**config)


def test_ai_disabled_needs_no_live_configuration() -> None:
    settings = Settings(**values())
    assert settings.ai.api_key is None
    assert settings.ai.model is None


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError):
        Settings(**(values("production") | {"debug": True}))


def test_cors_origins_default_to_local_frontend() -> None:
    config = values()
    del config["cors_origins"]
    assert Settings(**config).cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


@pytest.mark.parametrize("mode", ["local", "production"])
def test_cors_rejects_wildcard_origin(mode: str) -> None:
    with pytest.raises(ValidationError, match="wildcard CORS origin"):
        Settings(**(values(mode) | {"cors_origins": ["*"]}))


@pytest.mark.parametrize(
    "origins",
    [
        [],
        ["http://app.bizpilot.invalid"],
        ["https://localhost:3000"],
        ["app.bizpilot.invalid"],
    ],
)
def test_production_rejects_unsafe_cors_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError):
        Settings(**(values("production") | {"cors_origins": origins}))


def test_production_requires_explicit_cors_origins() -> None:
    config = values("production")
    del config["cors_origins"]
    with pytest.raises(ValidationError):
        Settings(**config)


def test_cors_origins_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIZPILOT_CORS_ORIGINS", '["https://app.bizpilot.invalid"]')
    config = values("production")
    del config["cors_origins"]
    assert Settings(**config).cors_origins == ["https://app.bizpilot.invalid"]


def test_email_defaults_disable_smtp() -> None:
    settings = Settings(**values())
    assert settings.email.smtp_enabled is False
    assert settings.email.smtp_security == "starttls"


@pytest.mark.parametrize(
    "email",
    [
        {"smtp_host": "smtp.mail.invalid"},
        {"smtp_host": "smtp.mail.invalid", "from_address": "no-reply@x.invalid", "smtp_username": "u"},
        {"frontend_base_url": "not-a-url"},
    ],
)
def test_email_rejects_incomplete_configuration(email: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**(values() | {"email": email}))


@pytest.mark.parametrize(
    "override",
    [
        {"smtp_host": None},
        {"smtp_security": "none"},
        {"frontend_base_url": "http://app.bizpilot.invalid"},
        {"smtp_password": "change-me-placeholder"},
    ],
)
def test_production_rejects_unsafe_email(override: dict[str, object]) -> None:
    config = values("production")
    config["email"] = production_email() | override
    with pytest.raises(ValidationError):
        Settings(**config)


def test_smtp_password_redacted_from_representations() -> None:
    settings = Settings(**values("production"))
    output = f"{settings!r} {settings.model_dump()}"
    assert "Sm7p_Relay_Credential_2026_Long" not in output


def test_production_rejects_insecure_transport() -> None:
    config = values("production")
    config["database"] = {"url": "postgresql://user:password@db.invalid/bizpilot"}
    with pytest.raises(ValidationError):
        Settings(**config)


@pytest.mark.parametrize("secret", ["short", "change-me-placeholder-secret-that-is-long"])
def test_production_rejects_placeholder_secret(secret: str) -> None:
    config = values("production")
    config["auth"] = {"signing_secret": secret}
    with pytest.raises(ValidationError):
        Settings(**config)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:password@db.invalid/bizpilot?sslmode=require",
        "postgresql://runtime_app@db.invalid/bizpilot?sslmode=require",
        "postgresql://runtime_app:%20%20@db.invalid/bizpilot?sslmode=require",
        "postgresql://runtime_app:%70assword@db.invalid/bizpilot?sslmode=require",
    ],
)
def test_production_rejects_missing_or_placeholder_database_secret(url: str) -> None:
    config = values("production")
    config["database"] = {"url": url}
    with pytest.raises(ValidationError):
        Settings(**config)


def test_process_environment_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join([
            "BIZPILOT_ENVIRONMENT=local",
            "BIZPILOT_DATABASE__URL=postgresql://dotenv:secret@localhost/dotenv",
            "BIZPILOT_AUTH__SIGNING_SECRET=dotenv-secret-value",
            "BIZPILOT_LOGGING__LEVEL=INFO",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setenv("BIZPILOT_LOGGING__LEVEL", "ERROR")
    assert Settings(_env_file=dotenv).logging.level == "ERROR"


def test_secrets_are_redacted_from_representations() -> None:
    settings = Settings(**values())
    output = f"{settings!r} {settings} {settings.model_dump()}"
    assert "secure-runtime-signing-secret-over-32-characters" not in output
    assert "db-secret-password" not in output


def test_secrets_are_absent_from_validation_errors() -> None:
    exposed_url = "not-postgresql://highly-sensitive-db-password@localhost/db"
    exposed_secret = "change-me-super-sensitive-signing-secret"
    config = values("production")
    config["database"] = {"url": exposed_url}
    config["auth"] = {"signing_secret": exposed_secret}
    with pytest.raises(ValidationError) as caught:
        Settings(**config)
    assert exposed_url not in str(caught.value)
    assert exposed_secret not in str(caught.value)


def test_unknown_nested_name_in_direct_input_is_rejected() -> None:
    config = values()
    config["ai"] = {"enabled": False, "api_keey": "typo"}
    with pytest.raises(ValidationError):
        Settings(**config)


def test_unknown_nested_name_in_dotenv_is_rejected(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join([
            "BIZPILOT_ENVIRONMENT=local",
            "BIZPILOT_DATABASE__URL=postgresql://dotenv:secret@localhost/dotenv",
            "BIZPILOT_AUTH__SIGNING_SECRET=dotenv-secret-value",
            "BIZPILOT_AI__API_KEEY=typo",
        ]),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=dotenv)


def test_unknown_application_name_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIZPILOT_DATABASE__PASSWORD", "must-not-be-ignored")
    with pytest.raises(ValueError, match="unknown BizPilot configuration"):
        Settings(**values())


def test_jwt_issuer_and_audience_defaults() -> None:
    settings = Settings(**values())
    assert settings.auth.jwt_issuer == "bizpilot-api"
    assert settings.auth.jwt_audience == "bizpilot-web"
    assert settings.auth.previous_signing_secrets == []


def test_previous_signing_secrets_parsing_and_masking() -> None:
    config = values()
    config["auth"] = {
        "signing_secret": "active-signing-secret-over-32-characters",
        "previous_signing_secrets": [
            "retired-signing-secret-1-over-32-chars",
            "retired-signing-secret-2-over-32-chars",
        ],
    }
    settings = Settings(**config)
    assert len(settings.auth.previous_signing_secrets) == 2
    assert (
        settings.auth.previous_signing_secrets[0].get_secret_value()
        == "retired-signing-secret-1-over-32-chars"
    )
    assert "retired-signing-secret-1" not in repr(settings.auth)


def test_previous_signing_secrets_blank_rejected() -> None:
    config = values()
    config["auth"] = {
        "signing_secret": "active-signing-secret-over-32-characters",
        "previous_signing_secrets": ["   "],
    }
    with pytest.raises(ValidationError, match="previous authentication signing secret must not be blank"):
        Settings(**config)


def test_production_rejects_placeholder_previous_signing_secret() -> None:
    config = values("production")
    config["auth"]["previous_signing_secrets"] = ["change-me-placeholder-secret-that-is-long"]
    with pytest.raises(ValueError, match="must be a non-placeholder value"):
        Settings(**config)


def test_auth_rate_limit_defaults_and_validation() -> None:
    settings = Settings(**values())
    assert settings.auth.rate_limit_window_minutes == 15
    assert settings.auth.login_max_failures == 5
    assert settings.auth.recovery_max_requests == 5

    config = values()
    config["auth"]["login_max_failures"] = 0
    with pytest.raises(ValidationError):
        Settings(**config)


def test_auth_rate_limit_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIZPILOT_AUTH__LOGIN_MAX_FAILURES", "10")
    config = values()
    del config["auth"]
    monkeypatch.setenv("BIZPILOT_AUTH__SIGNING_SECRET", "secure-runtime-signing-secret-over-32-characters")
    assert Settings(**config).auth.login_max_failures == 10


def test_refresh_token_days_default_and_validation() -> None:
    settings = Settings(**values())
    assert settings.auth.refresh_token_days == 30

    config = values()
    config["auth"]["refresh_token_days"] = 7
    settings_custom = Settings(**config)
    assert settings_custom.auth.refresh_token_days == 7

    config_invalid = values()
    config_invalid["auth"]["refresh_token_days"] = 0
    with pytest.raises(ValidationError):
        Settings(**config_invalid)

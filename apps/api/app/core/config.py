"""Typed environment configuration for the BizPilot backend."""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class EnvironmentMode(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, extra="forbid")
    url: SecretStr

    @model_validator(mode="after")
    def validate_url(self) -> "DatabaseSettings":
        parsed = urlsplit(self.url.get_secret_value())
        if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or not parsed.hostname:
            raise ValueError("database URL must be a valid PostgreSQL URL")
        return self


class AuthenticationSettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, extra="forbid")
    signing_secret: SecretStr
    access_token_minutes: int = Field(default=15, ge=1)
    password_min_length: int = Field(default=12, ge=8, le=128)
    password_max_length: int = Field(default=128, ge=64, le=1024)
    argon2_time_cost: int = Field(default=3, ge=1)
    argon2_memory_cost_kib: int = Field(default=65536, ge=8192)
    argon2_parallelism: int = Field(default=4, ge=1)
    jwt_issuer: str = "bizpilot-api"
    jwt_audience: str = "bizpilot-web"
    previous_signing_secrets: list[SecretStr] = Field(default_factory=list)
    refresh_token_days: int = Field(default=30, ge=1)
    password_reset_token_minutes: int = Field(default=15, ge=1, le=1440)
    rate_limit_window_minutes: int = Field(default=15, ge=1, le=1440)
    login_max_failures: int = Field(default=5, ge=1, le=1000)
    recovery_max_requests: int = Field(default=5, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_secret(self) -> "AuthenticationSettings":
        if not self.signing_secret.get_secret_value().strip():
            raise ValueError("authentication signing secret must not be blank")
        for prev in self.previous_signing_secrets:
            if not prev.get_secret_value().strip():
                raise ValueError("previous authentication signing secret must not be blank")
        return self


class AISettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, extra="forbid")
    enabled: bool = False
    api_key: SecretStr | None = None
    model: str | None = None
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    max_tool_calls: int = Field(default=5, ge=1, le=20)
    log_raw_prompts: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_enabled(self) -> "AISettings":
        if self.enabled and (
            self.api_key is None
            or not self.api_key.get_secret_value().strip()
            or not self.model
            or not self.model.strip()
        ):
            raise ValueError("AI API key and model are required when AI is enabled")
        return self


class LoggingSettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, extra="forbid")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = True



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIZPILOT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
        hide_input_in_errors=True,
    )

    environment: EnvironmentMode
    debug: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    database: DatabaseSettings
    auth: AuthenticationSettings
    ai: AISettings = Field(default_factory=AISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del settings_cls

        def checked_environment() -> dict[str, Any]:
            allowed = {
                "bizpilot_environment", "bizpilot_debug", "bizpilot_cors_origins",
                "bizpilot_database__url",
                "bizpilot_auth__signing_secret", "bizpilot_auth__access_token_minutes",
                "bizpilot_auth__password_min_length", "bizpilot_auth__password_max_length",
                "bizpilot_auth__argon2_time_cost", "bizpilot_auth__argon2_memory_cost_kib",
                "bizpilot_auth__argon2_parallelism",
                "bizpilot_auth__jwt_issuer", "bizpilot_auth__jwt_audience",
                "bizpilot_auth__previous_signing_secrets",
                "bizpilot_auth__refresh_token_days",
                "bizpilot_auth__rate_limit_window_minutes",
                "bizpilot_auth__login_max_failures",
                "bizpilot_auth__recovery_max_requests",
                "bizpilot_ai__enabled", "bizpilot_ai__api_key", "bizpilot_ai__model",

                "bizpilot_logging__level", "bizpilot_logging__json_logs",
            }
            unknown = sorted(
                name for name in os.environ
                if name.lower().startswith("bizpilot_") and name.lower() not in allowed
            )
            if unknown:
                raise ValueError(f"unknown BizPilot configuration name(s): {', '.join(unknown)}")
            return env_settings()

        return init_settings, checked_environment, dotenv_settings, file_secret_settings

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if any(origin.strip() == "*" for origin in self.cors_origins):
            raise ValueError("wildcard CORS origin is not allowed")
        if self.environment is not EnvironmentMode.PRODUCTION:
            return self
        if self.debug:
            raise ValueError("debug mode is not allowed in production")
        if not self.cors_origins:
            raise ValueError("production requires at least one CORS origin")
        for origin in self.cors_origins:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme != "https" or not parsed_origin.hostname:
                raise ValueError("production CORS origins must be absolute https origins")
            if parsed_origin.hostname in {"localhost", "127.0.0.1"}:
                raise ValueError("production CORS origins must not be loopback hosts")
        query = {
            key.lower(): values
            for key, values in parse_qs(urlsplit(self.database.url.get_secret_value()).query).items()
        }
        ssl_modes = query.get("sslmode", [])
        if not ssl_modes or ssl_modes[-1].lower() not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("production PostgreSQL transport must require TLS")
        parsed_database = urlsplit(self.database.url.get_secret_value())
        if not parsed_database.username or not parsed_database.password:
            raise ValueError("production PostgreSQL URL must include runtime credentials")
        self._reject_placeholder_text("database username", unquote(parsed_database.username))
        self._reject_placeholder_text("database password", unquote(parsed_database.password))
        self._reject_placeholder("authentication signing secret", self.auth.signing_secret)
        for prev in self.auth.previous_signing_secrets:
            self._reject_placeholder("previous authentication signing secret", prev)
        if self.ai.enabled and self.ai.api_key is not None:
            self._reject_placeholder("AI API key", self.ai.api_key)
        return self

    @classmethod
    def _reject_placeholder(cls, name: str, value: SecretStr) -> None:
        cls._reject_placeholder_text(name, value.get_secret_value(), minimum_length=32)

    @staticmethod
    def _reject_placeholder_text(
        name: str, value: str, minimum_length: int = 1
    ) -> None:
        secret = value.strip().lower()
        markers = (
            "placeholder", "change-me", "changeme", "example", "dummy",
            "your-", "password", "username",
        )
        if len(secret) < minimum_length or any(marker in secret for marker in markers):
            raise ValueError(f"production {name} must be a non-placeholder value")


@lru_cache
def get_settings() -> Settings:
    return Settings()

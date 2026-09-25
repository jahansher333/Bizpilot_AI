"""Unit tests for BizPilot AI Provider boundary and configuration (AI-001)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Request, Response
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import SecretStr, ValidationError

from app.core.config import AISettings
from app.modules.ai.exceptions import (
    AIConfigurationException,
    AIDisabledException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai.provider import AIProviderAdapter, get_ai_provider


def test_ai_provider_disabled_by_default() -> None:
    adapter = AIProviderAdapter(AISettings(enabled=False))
    assert not adapter.is_enabled
    assert adapter.model_name == "gpt-4o-mini"
    assert adapter.timeout_seconds == 30.0
    assert not adapter.log_raw_prompts

    with pytest.raises(AIDisabledException) as exc_info:
        adapter.get_client()

    assert exc_info.value.status_code == 503
    assert "disabled" in str(exc_info.value.message).lower()


def test_ai_provider_configuration_validation() -> None:
    # Enabled without key must fail validation
    with pytest.raises(ValidationError):
        AISettings(enabled=True, api_key=None, model="gpt-4o")

    # Enabled with empty string key must fail validation
    with pytest.raises(ValidationError):
        AISettings(enabled=True, api_key=SecretStr("   "), model="gpt-4o")

    # Enabled with empty model must fail validation
    with pytest.raises(ValidationError):
        AISettings(enabled=True, api_key=SecretStr("sk-test-secret-1234"), model="  ")


def test_ai_provider_client_initialization() -> None:
    settings = AISettings(
        enabled=True,
        api_key=SecretStr("sk-test-secret-1234567890"),
        model="gpt-4o-mini",
        timeout_seconds=15.0,
    )
    adapter = AIProviderAdapter(settings)
    assert adapter.is_enabled
    assert adapter.model_name == "gpt-4o-mini"
    assert adapter.timeout_seconds == 15.0

    client = adapter.get_client()
    assert client is not None
    assert client.api_key == "sk-test-secret-1234567890"
    assert client.timeout == 15.0


def test_ai_provider_repr_never_leaks_secrets() -> None:
    secret = "sk-super-secret-key-that-must-never-leak"
    settings = AISettings(
        enabled=True,
        api_key=SecretStr(secret),
        model="gpt-4o",
    )
    adapter = AIProviderAdapter(settings)
    repr_str = repr(adapter)

    assert secret not in repr_str
    assert "gpt-4o" in repr_str
    assert "enabled=True" in repr_str


@pytest.mark.asyncio
async def test_ai_provider_timeout_handling() -> None:
    adapter = AIProviderAdapter(
        AISettings(
            enabled=True,
            api_key=SecretStr("sk-test-123"),
            model="gpt-4o-mini",
            timeout_seconds=5.0,
        )
    )

    async def slow_operation() -> str:
        await asyncio.sleep(0.5)
        return "done"

    with pytest.raises(AITimeoutException) as exc_info:
        await adapter.execute_with_timeout(slow_operation(), custom_timeout=0.05)

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.message.lower()
    assert "unaffected" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_ai_provider_connection_error_mapping() -> None:
    adapter = AIProviderAdapter(
        AISettings(
            enabled=True,
            api_key=SecretStr("sk-test-123"),
            model="gpt-4o-mini",
        )
    )

    req = Request("POST", "https://api.openai.com/v1/chat/completions")

    async def failing_call() -> None:
        raise APIConnectionError(request=req, message="Connection failed")

    with pytest.raises(AIProviderUnavailableException) as exc_info:
        await adapter.execute_with_timeout(failing_call())

    assert exc_info.value.status_code == 503
    assert "temporarily unavailable" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_ai_provider_rate_limit_and_5xx_mapping() -> None:
    adapter = AIProviderAdapter(
        AISettings(
            enabled=True,
            api_key=SecretStr("sk-test-123"),
            model="gpt-4o-mini",
        )
    )

    req = Request("POST", "https://api.openai.com/v1/chat/completions")
    res = Response(status_code=429, request=req)

    async def rate_limited_call() -> None:
        raise RateLimitError("Rate limit exceeded", response=res, body=None)

    with pytest.raises(AIProviderUnavailableException) as exc_info:
        await adapter.execute_with_timeout(rate_limited_call())

    assert exc_info.value.status_code == 503

    res_500 = Response(status_code=500, request=req)

    async def server_error_call() -> None:
        raise InternalServerError("OpenAI internal error", response=res_500, body=None)

    with pytest.raises(AIProviderUnavailableException) as exc_info_500:
        await adapter.execute_with_timeout(server_error_call())

    assert exc_info_500.value.status_code == 503


def test_ai_provider_singleton_factory() -> None:
    provider1 = get_ai_provider()
    provider2 = get_ai_provider()
    assert provider1 is provider2

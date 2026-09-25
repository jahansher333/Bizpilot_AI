"""AI provider boundary and adapter for BizPilot Assistant (AI-001).

Implements the OpenAI Responses API / Agents SDK provider boundary with:
- Configurable model selection
- Strict timeout boundary
- Safe fallback during provider unavailability
- Secret credential encapsulation (never leaked to logs, client, or responses)
- Core application isolation
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.core.config import AISettings, Settings, get_settings
from app.modules.ai.exceptions import (
    AIConfigurationException,
    AIDisabledException,
    AIProviderUnavailableException,
    AITimeoutException,
)

logger = logging.getLogger("bizpilot.ai.provider")


class AIProviderAdapter:
    """Encapsulates the OpenAI provider boundary and client lifecycle."""

    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or get_settings().ai
        self._client: AsyncOpenAI | None = None

    @property
    def is_enabled(self) -> bool:
        """Indicates whether AI capabilities are enabled in the environment."""
        return self._settings.enabled

    @property
    def model_name(self) -> str:
        """Returns the configured model identifier."""
        if not self._settings.model:
            return "gpt-4o-mini"
        return self._settings.model

    @property
    def timeout_seconds(self) -> float:
        """Configured timeout limit in seconds for provider calls."""
        return self._settings.timeout_seconds

    @property
    def max_tool_calls(self) -> int:
        """Maximum number of tool call rounds allowed per assistant turn."""
        return self._settings.max_tool_calls

    @property
    def log_raw_prompts(self) -> bool:
        """Whether raw prompts and completions should be logged (default: False)."""
        return self._settings.log_raw_prompts

    def get_client(self) -> AsyncOpenAI:
        """Returns an initialized AsyncOpenAI client or raises if misconfigured/disabled."""
        if not self.is_enabled:
            raise AIDisabledException("BizPilot AI Assistant is currently disabled.")

        if self._settings.api_key is None or not self._settings.api_key.get_secret_value().strip():
            raise AIConfigurationException("OpenAI API key is missing or blank.")

        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._settings.api_key.get_secret_value(),
                timeout=self._settings.timeout_seconds,
                max_retries=1,
            )
        return self._client

    async def execute_with_timeout(
        self,
        coro: Any,
        custom_timeout: float | None = None,
    ) -> Any:
        """Executes an async AI provider coroutine protected by timeout and error translation."""
        timeout = custom_timeout or self.timeout_seconds

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            logger.warning("AI provider call timed out after %s seconds", timeout)
            raise AITimeoutException(
                f"The AI request timed out after {timeout:.1f}s. Core operations remain unaffected."
            ) from exc
        except APITimeoutError as exc:
            logger.warning("OpenAI APITimeoutError caught: %s", exc)
            raise AITimeoutException("The AI provider timed out. Core operations remain unaffected.") from exc
        except (APIConnectionError, RateLimitError, InternalServerError) as exc:
            logger.error("OpenAI provider communication failure: %s", type(exc).__name__)
            raise AIProviderUnavailableException(
                "The upstream AI provider is temporarily unavailable. Core operations remain unaffected."
            ) from exc
        except Exception as exc:
            if isinstance(exc, (AITimeoutException, AIProviderUnavailableException, AIDisabledException)):
                raise
            logger.error("Unexpected error in AI provider boundary: %s", type(exc).__name__)
            raise AIProviderUnavailableException("The AI assistant encountered an unexpected error.") from exc

    def __repr__(self) -> str:
        # Guarantee no secrets or keys leak in string representations
        return (
            f"<AIProviderAdapter enabled={self.is_enabled} model={self.model_name!r} "
            f"timeout={self.timeout_seconds}s>"
        )


_global_provider: AIProviderAdapter | None = None


def get_ai_provider(settings: Settings | None = None) -> AIProviderAdapter:
    """Dependency injector / factory for the AI provider boundary."""
    global _global_provider
    if _global_provider is None or settings is not None:
        ai_cfg = settings.ai if settings else get_settings().ai
        _global_provider = AIProviderAdapter(ai_cfg)
    return _global_provider

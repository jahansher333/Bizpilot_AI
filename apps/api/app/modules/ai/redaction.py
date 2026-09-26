"""Privacy-first redaction and sanitization utilities for BizPilot AI (AI-007).

Ensures that credentials, authorization tokens, passwords, database strings,
and arbitrary sensitive payload data are NEVER persisted to trace metadata or logs.
"""

from __future__ import annotations

import re
from typing import Any

# Regex patterns for sensitive values
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE)
_OPENAI_KEY_PATTERN = re.compile(r"sk-[a-zA-Z0-9_\-]{20,}")
_JWT_PATTERN = re.compile(r"ey[a-zA-Z0-9_\-]+\.ey[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+")
_CONN_STRING_PATTERN = re.compile(r"(postgresql(?:\+asyncpg)?://)([^:]+):([^@]+)@")
_SENSITIVE_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(password|secret|api[_-]?key|access_token|refresh_token)\s*[:=]\s*['\"]?([^'\"\s,;]+)['\"]?"
)

# Sensitive dictionary keys to mask
_SENSITIVE_KEY_NAMES = {
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credentials",
    "signing_secret",
}


def redact_sensitive_text(text: str | None) -> str:
    """Redact bearer tokens, API keys, JWTs, and database credentials from text."""
    if not text:
        return ""

    sanitized = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", text)
    sanitized = _OPENAI_KEY_PATTERN.sub("[API_KEY_REDACTED]", sanitized)
    sanitized = _JWT_PATTERN.sub("[JWT_REDACTED]", sanitized)
    sanitized = _CONN_STRING_PATTERN.sub(r"\1[REDACTED]:[REDACTED]@", sanitized)
    sanitized = _SENSITIVE_KEY_VALUE_PATTERN.sub(r'\1="[REDACTED]"', sanitized)
    return sanitized


def redact_dict(data: Any) -> Any:
    """Recursively redact dictionary keys and string values matching sensitive criteria."""
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            key_str = str(key).lower()
            if any(sensitive in key_str for sensitive in _SENSITIVE_KEY_NAMES):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_dict(value)
        return result
    elif isinstance(data, list):
        return [redact_dict(item) for item in data]
    elif isinstance(data, str):
        return redact_sensitive_text(data)
    else:
        return data


def sanitize_error_category(exc: Exception | None, default: str = "internal_error") -> str:
    """Safely categorize an error for metadata logging without emitting raw messages or traces."""
    if exc is None:
        return default
    cls_name = exc.__class__.__name__.lower()
    if "timeout" in cls_name:
        return "timeout"
    if "unavailable" in cls_name or "connection" in cls_name:
        return "provider_unavailable"
    if "permission" in cls_name or "denied" in cls_name or "unauthorized" in cls_name:
        return "authorization_denied"
    if "maxturn" in cls_name:
        return "max_turns_exceeded"
    if "disabled" in cls_name:
        return "disabled"
    if "validation" in cls_name:
        return "validation_error"
    return default

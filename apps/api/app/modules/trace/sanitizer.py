"""Defensive metadata sanitization and size enforcement engine (ORG-006).

Ensures all trace event metadata is stripped of credentials, tokens, secrets,
raw HTTP payloads, and AI generation data before storage, and strictly bounds
serialized payload size to 4096 UTF-8 bytes.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.core.errors import ValidationException

REDACTED_VALUE = "[REDACTED]"
MAX_METADATA_BYTES = 4096

# Substrings to flag in normalized keys
SENSITIVE_KEY_PATTERNS = (
    "password",
    "token",
    "jwt",
    "secret",
    "apikey",
    "privatekey",
    "authorization",
    "authheader",
    "authtoken",
    "authsecret",
    "cookie",
    "setcookie",
    "credential",
    "cvv",
    "cardnumber",
    "creditcard",
    "bankaccount",
    "iban",
    "prompt",
    "completion",
    "embedding",
    "requestbody",
    "responsebody",
)


def _normalize_key(key: str) -> str:
    """Normalize a key string by removing whitespace, hyphens, underscores and converting to lowercase."""
    return re.sub(r"[_\-\s]", "", key.lower())


def is_sensitive_key(key: str) -> bool:
    """Determine whether a metadata key represents sensitive data requiring redaction."""
    normalized = _normalize_key(key)
    return any(pattern in normalized for pattern in SENSITIVE_KEY_PATTERNS)


def _sanitize_value(val: Any) -> Any:
    """Recursively sanitize and serialize arbitrary values to JSON-safe primitives."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, dict):
        return _sanitize_dict(val)
    if isinstance(val, (list, tuple, set)):
        return [_sanitize_value(item) for item in val]
    # For arbitrary objects/classes (e.g. ORM models, functions), avoid calling __repr__ or __str__
    # which could leak internal memory or attribute values. Use safe deterministic placeholder.
    return "<unserializable>"


def _sanitize_dict(d: dict[Any, Any]) -> dict[str, Any]:
    """Recursively sanitize a dictionary, replacing sensitive keys' values with REDACTED_VALUE."""
    sanitized: dict[str, Any] = {}
    for raw_k, raw_v in d.items():
        key_str = str(raw_k)
        if is_sensitive_key(key_str):
            sanitized[key_str] = REDACTED_VALUE
        else:
            sanitized[key_str] = _sanitize_value(raw_v)
    return sanitized


def sanitize_and_validate_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively sanitize trace metadata and enforce the 4096-byte UTF-8 limit.

    Raises:
        ValidationException: If metadata is not a dictionary or serialized bytes exceed 4096.
    """
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValidationException("Trace metadata must be a dictionary")

    sanitized = _sanitize_dict(metadata)

    try:
        serialized = json.dumps(sanitized, ensure_ascii=False)
    except (TypeError, ValueError):
        raise ValidationException("Trace metadata could not be safely serialized to JSON")

    size_bytes = len(serialized.encode("utf-8"))
    if size_bytes > MAX_METADATA_BYTES:
        raise ValidationException(
            f"Trace metadata exceeds maximum size limit of {MAX_METADATA_BYTES} bytes"
        )

    return sanitized

"""Structured logging and sensitive data redaction for BizPilot."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.config import LoggingSettings

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "reset_token",
    "signing_secret",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "database_url",
    "url",
    "credentials",
}

REDACTED_TEXT = "[REDACTED]"


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive keys and values from dictionaries and collections."""
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS or any(s in str(k).lower() for s in ("secret", "password", "token", "api_key")):
                redacted[k] = REDACTED_TEXT
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    if isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_sensitive_data(item) for item in data)
    if isinstance(data, str):
        # Redact bearer tokens or basic auth strings if present in text
        if re.search(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", data, flags=re.IGNORECASE):
            return re.sub(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", r"\1[REDACTED]", data, flags=re.IGNORECASE)
    return data


class JsonLogFormatter(logging.Formatter):
    """Format logs as structured JSON with correlation ID and timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            log_entry.update(redact_sensitive_data(extra))

        return json.dumps(log_entry)


def configure_logging(settings: LoggingSettings | None = None) -> None:
    """Configure root logger with structured JSON or generic console formatter."""
    level = settings.level if settings else "INFO"
    json_logs = settings.json_logs if settings else True

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)

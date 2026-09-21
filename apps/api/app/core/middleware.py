"""Request correlation and structured logging middleware for BizPilot API."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.access")

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to inject or extract correlation ID for request tracing."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        incoming_id = (
            request.headers.get(CORRELATION_HEADER)
            or request.headers.get(REQUEST_ID_HEADER)
        )
        correlation_id = incoming_id.strip() if incoming_id and incoming_id.strip() else str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Unhandled exceptions will be caught by exception handler, but log error here if needed
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"{request.method} {request.url.path} failed in {duration_ms}ms",
                extra={"correlation_id": correlation_id},
            )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers[CORRELATION_HEADER] = correlation_id

        # Log request summary without sensitive payload data
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
            extra={
                "correlation_id": correlation_id,
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            },
        )

        return response

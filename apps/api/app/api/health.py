"""Health and readiness endpoints for BizPilot API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.db.engine import get_engine

logger = logging.getLogger("app.health")

router = APIRouter(tags=["Health"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
@router.get("/health", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness probe to confirm the process is running and accepting requests."""
    return {"status": "ok"}


@router.get("/readyz")
@router.get("/ready")
async def readyz(response: Response) -> dict[str, Any]:
    """Readiness probe verifying database connectivity."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.warning("Readiness probe database check failed: %s", type(exc).__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unavailable"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "database": "unexpected_result"}

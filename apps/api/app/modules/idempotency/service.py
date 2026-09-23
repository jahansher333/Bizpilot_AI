"""Idempotency service for retry-safe mutating operations (INV-004, ORD-004, PAY-003, EXP-002)."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException
from app.modules.idempotency.models import IdempotencyKey


def compute_request_hash(payload: BaseModel | dict[str, Any] | str | bytes | None) -> str:
    """Compute a deterministic SHA-256 hash for request payload."""
    if payload is None:
        raw_bytes = b""
    elif isinstance(payload, BaseModel):
        raw_bytes = payload.model_dump_json(exclude_unset=False).encode("utf-8")
    elif isinstance(payload, dict):
        raw_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        raw_bytes = payload
    else:
        raw_bytes = str(payload).encode("utf-8")

    return hashlib.sha256(raw_bytes).hexdigest()


class IdempotencyService:
    """Manages recording and replaying idempotency records within a database session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stored_response(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        operation: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[int, str] | None:
        """Check for existing idempotency key.

        Returns (response_code, response_payload) if an identical request was already processed.
        Raises ConflictException if key was reused with different request content.
        Returns None if key has not been used.
        """
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.organization_id == organization_id,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
        record = await self._session.scalar(stmt)
        if record is None:
            return None

        if record.request_hash != request_hash:
            raise ConflictException(
                f"Idempotency key '{idempotency_key}' was previously used with different parameters"
            )

        return (record.response_code or 200, record.response_payload or "")

    async def record_response(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        operation: str,
        idempotency_key: str,
        request_hash: str,
        response_code: int,
        response_payload: str,
    ) -> IdempotencyKey:
        """Persist a completed idempotency record."""
        record = IdempotencyKey(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            response_code=response_code,
            response_payload=response_payload,
        )
        self._session.add(record)
        return record

"""Refresh-token replay revocation survives the request rollback (SEC-P1).

Other refresh tests override get_session with a session that is never rolled back, which hid
that the replay branch revoked the family and then raised, so the production request scope
(session_scope) rolled the revocation back. This test uses the real request session lifecycle.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken
from app.modules.auth.refresh import hash_refresh_token
from tests.helpers import refresh_cookie, refresh_cookie_header

PASSWORD = "ValidSecretPassword123!"


@pytest.mark.asyncio
async def test_replayed_refresh_token_revokes_family_with_real_session_scope(
    test_app: FastAPI, db_engine, session_db_url: str
) -> None:
    email = f"replay_scope_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
        await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Replay"})
        first = refresh_cookie(await client.post("/api/auth/login", json={"email": email, "password": PASSWORD}))
        rotated = await client.post("/api/auth/refresh", headers=refresh_cookie_header(first))
        assert rotated.status_code == 200
        second = refresh_cookie(rotated)

        replay = await client.post("/api/auth/refresh", headers=refresh_cookie_header(first))
        assert replay.status_code == 401

        # The legitimate-looking successor must now be dead too: the theft response stuck.
        after = await client.post("/api/auth/refresh", headers=refresh_cookie_header(second))
        assert after.status_code == 401

    async with AsyncSession(db_engine) as check:
        row = (
            await check.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(second)))
        ).scalar_one()
        assert row.revoked_at is not None

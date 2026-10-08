"""Refresh reuse grace window (SEC-P1 F3 follow-up, founder decision 2026-10-09).

A page reloaded or left while its refresh was in flight never stores the rotated cookie and presents
the old token again. Within 20 seconds, and only while the successor has never been used, that is
treated as a lost response: the unused successor is retired and a fresh token issued. Every other
reuse is still replay and revokes the whole session family.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.modules.auth.models import RefreshToken
from app.modules.auth.refresh import hash_refresh_token
from tests.helpers import refresh_cookie, refresh_cookie_header

PASSWORD = "Reuse-Grace-2026!"


@pytest.fixture
def grace_app(test_settings: Settings, db_session: AsyncSession) -> FastAPI:
    auth = test_settings.auth.model_copy(update={"refresh_reuse_grace_seconds": 20})
    app = create_app(test_settings.model_copy(update={"auth": auth}))

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    return app


@pytest.fixture
async def client(grace_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=grace_app), base_url="http://testserver") as c:
        yield c


async def _login(client: AsyncClient) -> str:
    email = f"grace_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Grace"})
    return refresh_cookie(await client.post("/api/auth/login", json={"email": email, "password": PASSWORD}))


async def _refresh(client: AsyncClient, token: str):
    return await client.post("/api/auth/refresh", headers=refresh_cookie_header(token))


async def _row(db_session: AsyncSession, raw: str) -> RefreshToken:
    return (
        await db_session.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    ).scalar_one()


@pytest.mark.asyncio
async def test_lost_rotation_response_is_retried_without_ending_the_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    r1 = await _login(client)
    r2 = refresh_cookie(await _refresh(client, r1))  # the browser never stores r2 (navigation aborted)

    retry = await _refresh(client, r1)
    assert retry.status_code == 200
    r3 = refresh_cookie(retry)
    assert r3 not in (r1, r2)

    # The never-delivered r2 is retired; the session continues on r3.
    assert (await _row(db_session, r2)).revoked_at is not None
    assert (await _row(db_session, r3)).revoked_at is None
    assert (await _refresh(client, r3)).status_code == 200


@pytest.mark.asyncio
async def test_successor_already_used_means_replay_even_inside_the_window(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The theft case: the legitimate client used its new token, then the old one shows up again."""
    r1 = await _login(client)
    r2 = refresh_cookie(await _refresh(client, r1))
    r3 = refresh_cookie(await _refresh(client, r2))  # the legitimate client carries on

    replay = await _refresh(client, r1)
    assert replay.status_code == 401
    assert (await _row(db_session, r3)).revoked_at is not None  # whole family revoked
    assert (await _refresh(client, r3)).status_code == 401


@pytest.mark.asyncio
async def test_reuse_after_the_window_is_replay(client: AsyncClient, db_session: AsyncSession) -> None:
    r1 = await _login(client)
    r2 = refresh_cookie(await _refresh(client, r1))
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(r1))
        .values(revoked_at=datetime.now(timezone.utc) - timedelta(seconds=21))
    )

    assert (await _refresh(client, r1)).status_code == 401
    assert (await _row(db_session, r2)).revoked_at is not None


@pytest.mark.asyncio
async def test_repeated_retries_do_not_extend_the_window(client: AsyncClient, db_session: AsyncSession) -> None:
    r1 = await _login(client)
    await _refresh(client, r1)
    assert (await _refresh(client, r1)).status_code == 200  # first retry inside the window
    original_rotation = (await _row(db_session, r1)).revoked_at

    # The window keeps counting from the original rotation, not from each retry.
    assert (await _row(db_session, r1)).revoked_at == original_rotation
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(r1))
        .values(revoked_at=original_rotation - timedelta(seconds=21))
    )
    assert (await _refresh(client, r1)).status_code == 401


@pytest.mark.asyncio
async def test_logged_out_token_gets_no_grace(client: AsyncClient) -> None:
    r1 = await _login(client)
    r2 = refresh_cookie(await _refresh(client, r1))
    assert (await client.post("/api/auth/logout", headers=refresh_cookie_header(r2))).status_code == 200
    assert (await _refresh(client, r1)).status_code == 401
    assert (await _refresh(client, r2)).status_code == 401


@pytest.mark.asyncio
async def test_disabled_account_gets_no_grace(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.modules.auth.models import User

    r1 = await _login(client)
    await _refresh(client, r1)
    owner_id = (await _row(db_session, r1)).user_id
    await db_session.execute(update(User).where(User.id == owner_id).values(status="disabled"))
    assert (await _refresh(client, r1)).status_code == 401


@pytest.mark.asyncio
async def test_grace_zero_restores_strict_replay_detection(
    test_settings: Settings, db_session: AsyncSession
) -> None:
    app = create_app(test_settings)  # tests default to refresh_reuse_grace_seconds=0

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as strict:
        r1 = await _login(strict)
        r2 = refresh_cookie(await _refresh(strict, r1))
        assert (await _refresh(strict, r1)).status_code == 401
        assert (await _row(db_session, r2)).revoked_at is not None


def test_production_default_is_twenty_seconds() -> None:
    from app.core.config import AuthenticationSettings

    assert AuthenticationSettings(signing_secret="x" * 40).refresh_reuse_grace_seconds == 20

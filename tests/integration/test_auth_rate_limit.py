"""Integration tests for login and password-recovery rate limiting (FIX-003)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import RateLimitException
from app.db.session import get_session
from app.main import create_app
from app.modules.auth.models import AuthRateLimitBucket
from app.modules.auth.rate_limit import AuthRateLimiter, RateLimitScope, rate_limit_key_hash

PASSWORD = "ValidSecretPassword123!"


@pytest.fixture
def limited_settings(test_settings: Settings) -> Settings:
    auth = test_settings.auth.model_copy(
        update={"login_max_failures": 3, "recovery_max_requests": 3, "rate_limit_window_minutes": 15}
    )
    return test_settings.model_copy(update={"auth": auth})


@pytest.fixture
def limited_app(limited_settings: Settings, db_session: AsyncSession) -> FastAPI:
    app = create_app(limited_settings)

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    return app


def _client(app: FastAPI, ip: str = "203.0.113.10") -> AsyncClient:
    transport = ASGITransport(app=app, client=(ip, 50000))
    return AsyncClient(transport=transport, base_url="http://testserver")


async def _register(client: AsyncClient) -> str:
    email = f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Rate Limit User"},
    )
    assert resp.status_code == 202
    return email


@pytest.mark.asyncio
async def test_login_blocked_after_max_failures_even_with_correct_password(limited_app: FastAPI) -> None:
    async with _client(limited_app) as client:
        email = await _register(client)
        for _ in range(3):
            resp = await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
            assert resp.status_code == 401

        blocked = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_login_limit_is_non_enumerating(limited_app: FastAPI) -> None:
    async with _client(limited_app) as client:
        existing = await _register(client)
        missing = f"missing_{uuid.uuid4().hex[:8]}@example.com"
        statuses = {}
        for email in (existing, missing):
            for _ in range(3):
                await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
            blocked = await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
            statuses[email] = (blocked.status_code, blocked.json()["error"]["message"])
        assert statuses[existing] == statuses[missing]
        assert statuses[existing][0] == 429


@pytest.mark.asyncio
async def test_successful_login_clears_failure_counter(limited_app: FastAPI) -> None:
    async with _client(limited_app) as client:
        email = await _register(client)
        for _ in range(2):
            await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
        ok = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert ok.status_code == 200

        for _ in range(2):
            resp = await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
            assert resp.status_code == 401
        assert (await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_login_limit_is_scoped_to_email_and_ip(limited_app: FastAPI) -> None:
    async with _client(limited_app, ip="203.0.113.20") as attacker:
        email = await _register(attacker)
        for _ in range(3):
            await attacker.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
        assert (await attacker.post("/api/auth/login", json={"email": email, "password": PASSWORD})).status_code == 429

    async with _client(limited_app, ip="198.51.100.7") as owner:
        assert (await owner.post("/api/auth/login", json={"email": email, "password": PASSWORD})).status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_limited_per_email(limited_app: FastAPI) -> None:
    email = f"forgot_{uuid.uuid4().hex[:8]}@example.com"
    for index in range(3):
        async with _client(limited_app, ip=f"203.0.113.{30 + index}") as client:
            assert (await client.post("/api/auth/forgot-password", json={"email": email})).status_code == 200

    async with _client(limited_app, ip="203.0.113.99") as client:
        blocked = await client.post("/api/auth/forgot-password", json={"email": email})
        assert blocked.status_code == 429
        other = await client.post("/api/auth/forgot-password", json={"email": f"other_{email}"})
        assert other.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_limited_per_ip_including_invalid_tokens(limited_app: FastAPI) -> None:
    async with _client(limited_app, ip="203.0.113.40") as client:
        for _ in range(3):
            resp = await client.post(
                "/api/auth/reset-password",
                json={"token": "invalid-token-value-" + uuid.uuid4().hex, "new_password": "NewSecretPassword1!"},
            )
            assert resp.status_code == 401
        blocked = await client.post(
            "/api/auth/reset-password",
            json={"token": "invalid-token-value-" + uuid.uuid4().hex, "new_password": "NewSecretPassword1!"},
        )
        assert blocked.status_code == 429

    async with _client(limited_app, ip="203.0.113.41") as other_client:
        resp = await other_client.post(
            "/api/auth/reset-password",
            json={"token": "invalid-token-value-" + uuid.uuid4().hex, "new_password": "NewSecretPassword1!"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rate_limit_window_expiry_restarts_counter(
    limited_settings: Settings, db_session: AsyncSession
) -> None:
    current = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
    limiter = AuthRateLimiter(db_session, limited_settings, clock=lambda: current)
    email = f"window_{uuid.uuid4().hex[:8]}@example.com"

    for _ in range(3):
        await limiter.record_login_failure(email, "203.0.113.50")
    with pytest.raises(RateLimitException):
        await limiter.ensure_login_allowed(email, "203.0.113.50")

    current = current + timedelta(minutes=15, seconds=1)
    await limiter.ensure_login_allowed(email, "203.0.113.50")
    await limiter.record_login_failure(email, "203.0.113.50")

    key = rate_limit_key_hash(RateLimitScope.LOGIN_FAILURE, email, "203.0.113.50")
    bucket = (
        await db_session.execute(select(AuthRateLimitBucket).where(AuthRateLimitBucket.key_hash == key))
    ).scalar_one()
    assert bucket.attempt_count == 1


@pytest.mark.asyncio
async def test_rate_limit_rows_store_no_raw_subject(limited_app: FastAPI, db_session: AsyncSession) -> None:
    async with _client(limited_app, ip="203.0.113.60") as client:
        email = f"privacy_{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/api/auth/login", json={"email": email, "password": "WrongPassword999!"})
        await client.post("/api/auth/forgot-password", json={"email": email})

    rows = (await db_session.execute(select(AuthRateLimitBucket))).scalars().all()
    assert rows
    for row in rows:
        assert email not in row.key_hash
        assert "203.0.113.60" not in row.key_hash
        assert len(row.key_hash) == 64

"""Registration/refresh rate limits and the AI daily allowance per organization (SEC-P1 F4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.modules.ai.models import AIDailyUsage
from app.modules.ai.quota import AI_DAILY_LIMIT_MESSAGE, AIDailyQuota

PASSWORD = "ValidSecretPassword123!"


@pytest.fixture
def abuse_settings(test_settings: Settings) -> Settings:
    auth = test_settings.auth.model_copy(update={"register_max_requests": 3, "refresh_max_requests": 2})
    ai = test_settings.ai.model_copy(update={"daily_requests_per_organization": 2})
    return test_settings.model_copy(update={"auth": auth, "ai": ai})


@pytest.fixture
def abuse_app(abuse_settings: Settings, db_session: AsyncSession) -> FastAPI:
    app = create_app(abuse_settings)

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    return app


def _client(app: FastAPI, ip: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://testserver")


def _registration(prefix: str = "abuse") -> dict[str, str]:
    return {
        "email": f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        "password": PASSWORD,
        "display_name": "Abuse Limit User",
    }


@pytest.mark.asyncio
async def test_registration_is_limited_per_ip(abuse_app: FastAPI) -> None:
    async with _client(abuse_app, "203.0.113.150") as client:
        for _ in range(3):
            assert (await client.post("/api/auth/register", json=_registration())).status_code == 202
        blocked = await client.post("/api/auth/register", json=_registration())
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"

    async with _client(abuse_app, "198.51.100.150") as other:
        assert (await other.post("/api/auth/register", json=_registration())).status_code == 202


@pytest.mark.asyncio
async def test_registration_limit_counts_duplicate_and_invalid_attempts(abuse_app: FastAPI) -> None:
    """Every attempt counts, so the limit cannot be dodged with duplicates or rejected payloads."""
    payload = _registration()
    async with _client(abuse_app, "203.0.113.151") as client:
        assert (await client.post("/api/auth/register", json=payload)).status_code == 202
        assert (await client.post("/api/auth/register", json=payload)).status_code == 202
        weak = {**_registration(), "password": "password1234"}
        assert (await client.post("/api/auth/register", json=weak)).status_code == 422
        assert (await client.post("/api/auth/register", json=_registration())).status_code == 429


@pytest.mark.asyncio
async def test_refresh_is_limited_per_ip(abuse_app: FastAPI) -> None:
    async with _client(abuse_app, "203.0.113.152") as client:
        for _ in range(2):
            resp = await client.post("/api/auth/refresh", json={"refresh_token": "x" * 43})
            assert resp.status_code == 401
        blocked = await client.post("/api/auth/refresh", json={"refresh_token": "x" * 43})
        assert blocked.status_code == 429

    async with _client(abuse_app, "198.51.100.152") as other:
        assert (await other.post("/api/auth/refresh", json={"refresh_token": "x" * 43})).status_code == 401


async def _owner_with_org(client: AsyncClient, timezone_name: str = "Asia/Karachi") -> tuple[str, str]:
    payload = _registration("ai_quota")
    assert (await client.post("/api/auth/register", json=payload)).status_code == 202
    login = await client.post("/api/auth/login", json={"email": payload["email"], "password": PASSWORD})
    token = login.json()["access_token"]
    org = await client.post(
        "/api/organizations",
        json={"display_name": "Quota Traders", "timezone": timezone_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert org.status_code == 201
    return token, org.json()["id"]


@pytest.mark.asyncio
async def test_ai_chat_refused_after_daily_allowance(abuse_app: FastAPI) -> None:
    async with _client(abuse_app, "203.0.113.153") as client:
        token, org_id = await _owner_with_org(client)
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(2):
            resp = await client.post(f"/api/organizations/{org_id}/ai/chat", json={"message": "Sales today?"}, headers=headers)
            assert resp.status_code == 200
        blocked = await client.post(f"/api/organizations/{org_id}/ai/chat", json={"message": "Sales today?"}, headers=headers)
        assert blocked.status_code == 429
        assert blocked.json()["error"]["message"] == AI_DAILY_LIMIT_MESSAGE


@pytest.mark.asyncio
async def test_ai_allowance_is_per_organization(abuse_app: FastAPI) -> None:
    async with _client(abuse_app, "203.0.113.154") as client:
        token_a, org_a = await _owner_with_org(client)
        token_b, org_b = await _owner_with_org(client)
        for _ in range(2):
            await client.post(f"/api/organizations/{org_a}/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token_a}"})
        assert (
            await client.post(f"/api/organizations/{org_a}/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token_a}"})
        ).status_code == 429
        assert (
            await client.post(f"/api/organizations/{org_b}/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token_b}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_ai_allowance_not_consumed_by_unauthorized_callers(abuse_app: FastAPI) -> None:
    """Non-members are rejected by tenant context before the allowance is touched."""
    async with _client(abuse_app, "203.0.113.155") as client:
        token_owner, org_id = await _owner_with_org(client)
        token_outsider, _ = await _owner_with_org(client)
        for _ in range(5):
            resp = await client.post(
                f"/api/organizations/{org_id}/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token_outsider}"}
            )
            assert resp.status_code == 404
        assert (
            await client.post(f"/api/organizations/{org_id}/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token_owner}"})
        ).status_code == 200


@pytest.mark.asyncio
async def test_ai_allowance_resets_at_the_organizations_local_midnight(
    abuse_settings: Settings, abuse_app: FastAPI, db_session: AsyncSession
) -> None:
    async with _client(abuse_app, "203.0.113.156") as client:
        _, org_id = await _owner_with_org(client, timezone_name="Asia/Karachi")
    organization_id = uuid.UUID(org_id)
    now = {"value": datetime(2026, 10, 8, 18, 30, tzinfo=timezone.utc)}  # 23:30 in Karachi (UTC+5)
    quota = AIDailyQuota(db_session, abuse_settings, clock=lambda: now["value"])

    assert await quota.consume(organization_id, "Asia/Karachi")
    assert await quota.consume(organization_id, "Asia/Karachi")
    assert not await quota.consume(organization_id, "Asia/Karachi")

    now["value"] = datetime(2026, 10, 8, 19, 1, tzinfo=timezone.utc)  # 00:01 on 9 October in Karachi
    assert await quota.consume(organization_id, "Asia/Karachi")

    rows = (
        await db_session.execute(
            select(AIDailyUsage.usage_date, AIDailyUsage.request_count)
            .where(AIDailyUsage.organization_id == organization_id)
            .order_by(AIDailyUsage.usage_date)
        )
    ).all()
    assert [(str(row.usage_date), row.request_count) for row in rows] == [("2026-10-08", 3), ("2026-10-09", 1)]

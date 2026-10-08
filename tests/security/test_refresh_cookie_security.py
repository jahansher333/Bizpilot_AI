"""Refresh-token cookie transport (SEC-P1 F3).

- The refresh token is only ever an HttpOnly; Secure; SameSite=Strict cookie scoped to /api/auth.
- No response body carries it, so page scripts (or injected ones) cannot read it.
- Endpoints that act on the cookie refuse browser requests from origins outside the CORS list.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from tests.helpers import refresh_cookie, refresh_cookie_header

PASSWORD = "ValidSecretPassword123!"
WEB_ORIGIN = "https://app.bizpilot.test"


@pytest.fixture
def cookie_app(test_settings: Settings, db_session: AsyncSession) -> FastAPI:
    app = create_app(test_settings.model_copy(update={"cors_origins": [WEB_ORIGIN]}))

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    return app


@pytest.fixture
async def client(cookie_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=cookie_app), base_url="https://api.bizpilot.test") as c:
        yield c


async def _login(client: AsyncClient):
    email = f"cookie_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Cookie"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return resp


def _cookie_attributes(response) -> dict[str, str]:
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith("bizpilot_refresh="))
    attributes: dict[str, str] = {}
    for part in header.split(";")[1:]:
        name, _, value = part.strip().partition("=")
        attributes[name.lower()] = value
    return attributes


@pytest.mark.asyncio
async def test_login_sets_hardened_cookie_and_keeps_token_out_of_body(client: AsyncClient) -> None:
    resp = await _login(client)
    body = resp.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    token = refresh_cookie(resp)
    assert len(token) >= 43
    assert token not in resp.text

    attrs = _cookie_attributes(resp)
    assert "httponly" in attrs
    assert "secure" in attrs
    assert attrs["samesite"].lower() == "strict"
    assert attrs["path"] == "/api/auth"
    # Lives as long as the token family (30 days by default), never longer.
    assert 0 < int(attrs["max-age"]) <= 30 * 24 * 3600


@pytest.mark.asyncio
async def test_refresh_rotates_the_cookie_and_keeps_the_family_ceiling(client: AsyncClient) -> None:
    login = await _login(client)
    first = refresh_cookie(login)
    first_max_age = int(_cookie_attributes(login)["max-age"])

    rotated = await client.post("/api/auth/refresh", headers=refresh_cookie_header(first))
    assert rotated.status_code == 200
    assert set(rotated.json()) == {"access_token", "token_type", "expires_in"}
    second = refresh_cookie(rotated)
    assert second != first
    assert int(_cookie_attributes(rotated)["max-age"]) <= first_max_age


@pytest.mark.asyncio
async def test_logout_revokes_and_clears_the_cookie(client: AsyncClient) -> None:
    token = refresh_cookie(await _login(client))
    out = await client.post("/api/auth/logout", headers=refresh_cookie_header(token))
    assert out.status_code == 200
    attrs = _cookie_attributes(out)
    assert attrs["max-age"] == "0"
    assert attrs["path"] == "/api/auth"
    assert (await client.post("/api/auth/refresh", headers=refresh_cookie_header(token))).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_clears_the_cookie(client: AsyncClient) -> None:
    login = await _login(client)
    out = await client.post(
        "/api/auth/logout-all", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert out.status_code == 200
    assert _cookie_attributes(out)["max-age"] == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["/api/auth/refresh", "/api/auth/logout"])
async def test_cookie_endpoints_reject_foreign_origins(client: AsyncClient, endpoint: str) -> None:
    """A page on another origin (even a same-site subdomain) cannot drive the cookie."""
    token = refresh_cookie(await _login(client))
    for origin in ("https://evil.example", "https://blog.bizpilot.test", "null"):
        resp = await client.post(endpoint, headers={**refresh_cookie_header(token), "Origin": origin})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"
    # The token was never used by the rejected requests, so the real app can still refresh.
    ok = await client.post("/api/auth/refresh", headers={**refresh_cookie_header(token), "Origin": WEB_ORIGIN})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_credentialed_cors_only_for_the_web_origin(client: AsyncClient) -> None:
    allowed = await client.options(
        "/api/auth/refresh", headers={"Origin": WEB_ORIGIN, "Access-Control-Request-Method": "POST"}
    )
    assert allowed.headers.get("access-control-allow-origin") == WEB_ORIGIN
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    denied = await client.options(
        "/api/auth/refresh", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in denied.headers

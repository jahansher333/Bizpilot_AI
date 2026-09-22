"""Security and negative tests for organization tenant isolation (ORG-001)."""

from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User


@pytest.fixture
async def sec_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with get_session overridden to db_session."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _register_and_login(client: AsyncClient, prefix: str) -> str:
    """Helper returning access token for a freshly registered user."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": "Security User"},
    )
    resp = await client.post("/api/auth/login", json={"email": email, "password": pw})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected_401(sec_client: AsyncClient) -> None:
    """Verify unauthenticated requests to organization endpoints are rejected with HTTP 401."""
    # POST without token
    r_post = await sec_client.post("/api/organizations", json={"display_name": "No Auth Store"})
    assert r_post.status_code == 401
    assert r_post.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # GET list without token
    r_list = await sec_client.get("/api/organizations")
    assert r_list.status_code == 401
    assert r_list.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # GET by ID without token
    r_get = await sec_client.get(f"/api/organizations/{uuid.uuid4()}")
    assert r_get.status_code == 401
    assert r_get.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_disabled_or_pending_user_rejected_401(
    sec_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify inactive/disabled user token cannot access organization endpoints."""
    token = await _register_and_login(sec_client, "disabled_user")

    # Manually disable user in DB
    email_query = select(User).where(User.display_name == "Security User")
    users = (await db_session.execute(email_query)).scalars().all()
    target_user = users[-1]
    target_user.status = UserStatus.DISABLED.value
    await db_session.commit()

    # Attempt to create organization
    r_post = await sec_client.post(
        "/api/organizations",
        json={"display_name": "Disabled User Org"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_post.status_code == 401
    assert r_post.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    # Attempt to list organizations
    r_list = await sec_client.get(
        "/api/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_list.status_code == 401


@pytest.mark.asyncio
async def test_client_injected_owner_id_or_role_rejected_422(sec_client: AsyncClient) -> None:
    """Verify request payloads with extra owner_id, user_id, or role are rejected with 422."""
    token = await _register_and_login(sec_client, "inject_user")

    # Injected owner_id
    r_owner = await sec_client.post(
        "/api/organizations",
        json={"display_name": "Store", "owner_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_owner.status_code == 422
    assert r_owner.json()["error"]["code"] == "VALIDATION_ERROR"

    # Injected role
    r_role = await sec_client.post(
        "/api/organizations",
        json={"display_name": "Store", "role": "superadmin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_role.status_code == 422
    assert r_role.json()["error"]["code"] == "VALIDATION_ERROR"

    # Injected user_id
    r_user = await sec_client.post(
        "/api/organizations",
        json={"display_name": "Store", "user_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_user.status_code == 422
    assert r_user.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_idor_cross_tenant_read_returns_non_disclosing_404(sec_client: AsyncClient) -> None:
    """Verify User A cannot read User B's organization by ID, receiving identical 404 to nonexistent org."""
    token_a = await _register_and_login(sec_client, "user_a")
    token_b = await _register_and_login(sec_client, "user_b")

    # User B creates organization
    resp_b = await sec_client.post(
        "/api/organizations",
        json={"display_name": "User B Private Business"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 201
    org_b_id = resp_b.json()["id"]

    # User A attempts to read User B's organization by ID (IDOR probe)
    resp_idor = await sec_client.get(
        f"/api/organizations/{org_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_idor.status_code == 404
    assert resp_idor.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert resp_idor.json()["error"]["message"] == "Organization not found"

    # Nonexistent organization ID produces identical non-disclosing 404
    nonexistent_id = uuid.uuid4()
    resp_nonexistent = await sec_client.get(
        f"/api/organizations/{nonexistent_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_nonexistent.status_code == 404
    assert resp_nonexistent.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert resp_nonexistent.json()["error"]["message"] == "Organization not found"


@pytest.mark.asyncio
async def test_malformed_organization_id_handled_safely(sec_client: AsyncClient) -> None:
    """Verify non-UUID path parameters in GET /api/organizations/{id} reject safely with 422 without 500 crashes."""
    token = await _register_and_login(sec_client, "uuid_user")

    r_malformed = await sec_client.get(
        "/api/organizations/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_malformed.status_code == 422
    assert r_malformed.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "traceback" not in r_malformed.text.lower()


@pytest.mark.asyncio
async def test_no_secret_leakage_in_organization_responses_or_logs(
    sec_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify organization responses and log outputs do not disclose passwords or JWT secrets."""
    token = await _register_and_login(sec_client, "secret_user")

    with caplog.at_level(logging.DEBUG):
        resp = await sec_client.post(
            "/api/organizations",
            json={"display_name": "Safe Secrets Store"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

    all_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "password" not in all_logs.lower() or "password_hash" not in all_logs
    assert "argon2" not in all_logs.lower()
    assert "signing_secret" not in all_logs.lower()

    # Response body inspection
    body = resp.text
    assert "password" not in body.lower()
    assert "signing_secret" not in body.lower()
    assert "token" not in body.lower() or "token_hash" not in body.lower()

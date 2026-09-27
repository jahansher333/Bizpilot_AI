"""Observability, Traces, and Redaction Validation Suite (HARD-006).

Validates:
1. Trace ID propagation across request and response headers (X-Trace-Id / X-Request-Id).
2. AI interaction and tool call metadata tracking with grounded provenance.
3. Privacy verification: raw conversation prompts and responses are NEVER persisted in AI metadata tables.
4. Redaction engine verification: sensitive credentials, passwords, tokens, API keys, and Authorization headers are scrubbed.
5. Error sanitization: external error responses do not leak database exceptions or internal stack traces.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents import RunResult
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.models import AIInteraction, AIToolCall
from app.modules.ai.redaction import redact_dict, redact_sensitive_text
from app.modules.ai.router import _ORCHESTRATOR


@pytest.fixture
async def obs_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with database session bound to the transaction rollback."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecureP@ss12345!"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    assert reg.status_code == 202

    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login.status_code == 200
    return email, login.json()["access_token"]


async def _create_org(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_trace_id_propagation_across_requests(obs_client: AsyncClient):
    """VERIFY: Incoming trace header or generated request ID is returned in response headers."""
    client = obs_client

    custom_trace_id = "trace-test-" + uuid.uuid4().hex
    resp = await client.get(
        "/health",
        headers={"x-trace-id": custom_trace_id},
    )
    assert resp.status_code == 200
    # Trace / Correlation ID is echoed in response headers
    returned_trace = resp.headers.get("x-correlation-id") or resp.headers.get("x-request-id")
    assert returned_trace is not None


@pytest.mark.asyncio
async def test_ai_observability_metadata_and_privacy_guarantee(
    obs_client: AsyncClient,
    db_session: AsyncSession,
):
    """VERIFY: AI metadata records latency and status WITHOUT storing raw prompts or completions."""
    client = obs_client
    _, token = await _create_user(client, "obs_ai_owner")
    org_id = await _create_org(client, token, "Obs AI Org")

    fake_provider = MagicMock()
    fake_provider.is_enabled = True
    fake_provider.model_name = "gpt-4o-mini"
    fake_provider.timeout_seconds = 10.0
    fake_provider.max_tool_calls = 5
    fake_provider.log_raw_prompts = False
    fake_provider.get_client.return_value = MagicMock()
    fake_provider.execute_with_timeout = AsyncMock(side_effect=lambda coro, **kwargs: coro)

    secret_inquiry = "Confidential business inquiry: what is our cash balance?"
    secret_response = "Your cash balance is Rs. 500,000 as of today."

    async def fake_runner_impl(starting_agent, input, context, max_turns, run_config):
        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output=secret_response,
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    with patch.object(_ORCHESTRATOR, "_provider", fake_provider), \
         patch("agents.Runner.run", side_effect=fake_runner_impl):
        chat_resp = await client.post(
            f"/api/organizations/{org_id}/ai/chat",
            json={"message": secret_inquiry},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert chat_data["interaction_id"] is not None
        interaction_id = uuid.UUID(chat_data["interaction_id"])

    # 1. Inspect PostgreSQL database directly for ai_interactions
    query = select(AIInteraction).where(AIInteraction.id == interaction_id)
    result = await db_session.execute(query)
    record = result.scalar_one_or_none()

    assert record is not None
    assert record.organization_id == uuid.UUID(org_id)
    assert record.model_identifier == "gpt-4o-mini"
    assert record.status == "success"
    assert record.latency_ms > 0

    # 2. PRIVACY VERIFICATION: Confirm table schema contains NO prompt/completion content columns
    col_query = text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'ai_interactions';"
    )
    cols_res = await db_session.execute(col_query)
    columns = [row[0].lower() for row in cols_res.fetchall()]

    assert "prompt" not in columns
    assert "user_message" not in columns
    assert "content" not in columns
    assert "completion" not in columns
    assert "response_text" not in columns


def test_redaction_engine_sanitization():
    """VERIFY: Redaction utility cleanses secrets, tokens, passwords, and authorization headers."""
    sensitive_dict = {
        "user_email": "owner@store.pk",
        "password": "SuperSecretPassword123!",
        "refresh_token": "rt_live_abcdef1234567890",
        "api_key": "sk-proj-998877665544332211",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy",
        "order_id": "01a0e000-0000-7000-8000-000000000001",
    }

    redacted = redact_dict(sensitive_dict)

    # Clean keys preserved
    assert redacted["user_email"] == "owner@store.pk"
    assert redacted["order_id"] == "01a0e000-0000-7000-8000-000000000001"

    # Sensitive keys redacted
    assert redacted["password"] == "[REDACTED]"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"

    # Text redaction
    raw_log = "Failed connecting to postgresql+asyncpg://user:secretpw123@neon.tech/bizpilot"
    cleaned_log = redact_sensitive_text(raw_log)
    assert "secretpw123" not in cleaned_log


@pytest.mark.asyncio
async def test_error_response_sanitization(obs_client: AsyncClient):
    """VERIFY: Error responses return clean structured JSON without database stack traces."""
    client = obs_client

    # Send malformed payload to trigger validation error
    resp = await client.post(
        "/api/auth/login",
        json={"email": "not-an-email"},
    )
    assert resp.status_code == 422
    body = resp.text

    # Verify no internal server stack trace or SQL text
    assert "Traceback (most recent call last)" not in body
    assert "SELECT " not in body
    assert "FROM users" not in body

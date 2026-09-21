"""Integration tests for health and readiness endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.health import router as health_router
from app.core.config import Settings
from app.main import create_app


def test_healthz_liveness(test_app) -> None:
    with TestClient(test_app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        response_alt = client.get("/health")
        assert response_alt.status_code == 200
        assert response_alt.json() == {"status": "ok"}


def test_readyz_readiness(test_app) -> None:
    with TestClient(test_app) as client:
        response = client.get("/readyz")
        # In real connected test environment, ready returns 200
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "connected"}


def test_readyz_database_failure_returns_503(monkeypatch: pytest.MonkeyPatch, test_settings: Settings) -> None:
    from sqlalchemy.ext.asyncio import AsyncEngine

    # Mock get_engine to simulate a broken connection
    class BrokenEngine:
        def connect(self):
            raise ConnectionRefusedError("Database unreachable")

    import app.api.health
    monkeypatch.setattr(app.api.health, "get_engine", lambda: BrokenEngine())

    app = create_app(test_settings)
    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unavailable"

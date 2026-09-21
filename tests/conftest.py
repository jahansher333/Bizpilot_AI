from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import dotenv_values
env_file = REPO_ROOT / ".env"
if env_file.exists():
    env_vals = dotenv_values(env_file)
    if "BIZPILOT_DATABASE__URL" in env_vals and "BIZPILOT_DATABASE__URL" not in os.environ:
        os.environ["BIZPILOT_DATABASE__URL"] = env_vals["BIZPILOT_DATABASE__URL"]

os.environ.setdefault("BIZPILOT_ENVIRONMENT", "test")
os.environ.setdefault("BIZPILOT_DATABASE__URL", "postgresql://test_user:test_password@localhost/bizpilot_test")
os.environ.setdefault("BIZPILOT_AUTH__SIGNING_SECRET", "test-only-signing-secret")

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database={"url": "postgresql://test_user:test_password@localhost/bizpilot_test"},
        auth={"signing_secret": "test-only-signing-secret"},
        ai={"enabled": False},
        logging={"level": "INFO", "json_logs": False},
    )


@pytest.fixture
def test_app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
def client(test_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(test_app) as test_client:
        yield test_client


from collections.abc import AsyncIterator
import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.engine import normalize_database_url
from tests.helpers import TwoOrganizationContext, build_two_organization_context


@pytest.fixture
def two_org_context() -> TwoOrganizationContext:
    return build_two_organization_context()


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(scope="session")
def session_db_url() -> str:
    url = os.environ.get("BIZPILOT_DATABASE__URL")
    if not url or "test_user:test_password" in url:
        pytest.skip("No real isolated test database available in BIZPILOT_DATABASE__URL")
    return normalize_database_url(url)


@pytest.fixture
async def db_engine(session_db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(session_db_url, poolclass=NullPool, future=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Provide a transaction-isolated session that automatically rolls back after each test."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        session = session_factory()
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
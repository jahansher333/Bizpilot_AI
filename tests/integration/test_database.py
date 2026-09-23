from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.base import Base, NAMING_CONVENTION
from app.db.engine import normalize_database_url
from app.db.session import AsyncSessionFactory, session_scope

# On Windows, psycopg async requires a compatible event loop selector
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_test_db_url() -> str:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    env_vals = dotenv_values(env_file) if env_file.exists() else {}
    url = os.environ.get("BIZPILOT_DATABASE__URL") or env_vals.get("BIZPILOT_DATABASE__URL")
    if not url:
        pytest.skip("BIZPILOT_DATABASE__URL not set in environment or .env")
    return normalize_database_url(url)


@pytest.fixture
def db_url() -> str:
    return get_test_db_url()


@pytest.fixture
async def async_engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(db_url, poolclass=NullPool, future=True)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_connection(async_engine: AsyncEngine) -> None:
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_transaction_rollback_discards_changes(async_engine: AsyncEngine) -> None:
    # Test that an uncommitted or rolled-back transaction discards state
    temp_table = "test_rollback_sentinel"

    # Clean up table if it existed from any previous run
    async with async_engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
        await conn.execute(text(f"CREATE TABLE {temp_table} (id INT PRIMARY KEY, val TEXT)"))

    try:
        # Start a transaction and force an exception to trigger rollback
        with pytest.raises(RuntimeError):
            async with async_engine.begin() as conn:
                await conn.execute(
                    text(f"INSERT INTO {temp_table} (id, val) VALUES (1, 'rollback_me')")
                )
                raise RuntimeError("Simulated failure to force transaction rollback")

        # Verify the record was discarded
        async with async_engine.connect() as conn:
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {temp_table}"))
            assert result.scalar() == 0
    finally:
        # Clean up temporary table
        async with async_engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))


@pytest.mark.asyncio
async def test_session_scope_commit_and_rollback(async_engine: AsyncEngine) -> None:
    session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Verify session_scope commits successfully
    temp_table = "test_session_scope_sentinel"
    async with async_engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
        await conn.execute(text(f"CREATE TABLE {temp_table} (id INT PRIMARY KEY, name TEXT)"))

    try:
        # Commit branch
        async with session_scope(session_maker) as session:
            await session.execute(
                text(f"INSERT INTO {temp_table} (id, name) VALUES (1, 'committed')")
            )

        async with async_engine.connect() as conn:
            res = await conn.execute(text(f"SELECT name FROM {temp_table} WHERE id = 1"))
            assert res.scalar() == "committed"

        # Rollback branch on error
        with pytest.raises(ValueError):
            async with session_scope(session_maker) as session:
                await session.execute(
                    text(f"INSERT INTO {temp_table} (id, name) VALUES (2, 'aborted')")
                )
                raise ValueError("Forced error inside session_scope")

        async with async_engine.connect() as conn:
            res = await conn.execute(text(f"SELECT COUNT(*) FROM {temp_table} WHERE id = 2"))
            assert res.scalar() == 0
    finally:
        async with async_engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))


def test_base_metadata_naming_convention() -> None:
    assert Base.metadata.naming_convention is not None
    assert Base.metadata.naming_convention["ix"] == "ix_%(column_0_label)s"
    assert Base.metadata.naming_convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert Base.metadata.naming_convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
    assert Base.metadata.naming_convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"


def test_alembic_configuration_and_head_revision() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ini_path = repo_root / "alembic.ini"
    assert ini_path.exists(), "alembic.ini must exist in repo root"

    cfg = Config(str(ini_path))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {heads}"
    assert heads[0] == "0006_products"


@pytest.mark.asyncio
async def test_clean_database_smoke(async_engine: AsyncEngine) -> None:
    # Verify that the database connection can query schema and no corrupted state exists
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT version(), current_database(), current_schema()")
        )
        row = result.fetchone()
        assert row is not None
        assert "PostgreSQL" in row[0]

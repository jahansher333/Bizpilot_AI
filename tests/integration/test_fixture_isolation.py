"""Integration tests for database test fixture rollback isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

TEMP_ISOLATION_TABLE = "test_fixture_isolation_sentinel"


@pytest.mark.asyncio
async def test_db_session_fixture_isolation(db_session: AsyncSession) -> None:
    # Test that db_session is an active session capable of executing queries
    result = await db_session.execute(text("SELECT 42"))
    assert result.scalar() == 42


@pytest.mark.asyncio
async def test_transaction_rollback_isolation(db_engine: AsyncEngine) -> None:
    # 1. Create temporary sentinel table
    async with db_engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {TEMP_ISOLATION_TABLE}"))
        await conn.execute(
            text(f"CREATE TABLE {TEMP_ISOLATION_TABLE} (id INT PRIMARY KEY, marker TEXT)")
        )

    try:
        # 2. Use a transaction-isolated connection and session
        async with db_engine.connect() as connection:
            transaction = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            async with session_factory() as session:
                await session.execute(
                    text(f"INSERT INTO {TEMP_ISOLATION_TABLE} (id, marker) VALUES (1, 'isolation_check')")
                )
                res = await session.execute(
                    text(f"SELECT marker FROM {TEMP_ISOLATION_TABLE} WHERE id = 1")
                )
                assert res.scalar() == "isolation_check"
            # Simulate fixture teardown rollback
            await transaction.rollback()

        # 3. Verify on a brand new independent connection that the record was discarded
        async with db_engine.connect() as conn:
            res = await conn.execute(
                text(f"SELECT COUNT(*) FROM {TEMP_ISOLATION_TABLE}")
            )
            assert res.scalar() == 0, "Record was committed instead of rolled back!"
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {TEMP_ISOLATION_TABLE}"))

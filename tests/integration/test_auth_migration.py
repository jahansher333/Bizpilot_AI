"""Integration tests verifying Alembic migration schema structure in PostgreSQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_auth_tables_exist(db_session: AsyncSession) -> None:
    """Verify all four AUTH-001 tables exist in the PostgreSQL database."""
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('users', 'user_credentials', 'refresh_tokens', 'password_reset_tokens')
        ORDER BY table_name;
        """
    )
    result = await db_session.execute(query)
    tables = {row[0] for row in result.fetchall()}
    assert tables == {"users", "user_credentials", "refresh_tokens", "password_reset_tokens"}


@pytest.mark.asyncio
async def test_users_table_columns_and_constraints(db_session: AsyncSession) -> None:
    """Verify columns and check constraint on users table."""
    col_query = text(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY column_name;
        """
    )
    res = await db_session.execute(col_query)
    cols = {row[0]: (row[1], row[2]) for row in res.fetchall()}

    assert "id" in cols
    assert cols["id"][0] == "uuid"
    assert cols["id"][1] == "NO"

    assert "email_normalized" in cols
    assert cols["email_normalized"][1] == "NO"

    assert "status" in cols
    assert cols["status"][1] == "NO"

    assert "created_at" in cols
    assert cols["created_at"][0] == "timestamp with time zone"

    assert "updated_at" in cols
    assert cols["updated_at"][0] == "timestamp with time zone"

    assert "last_login_at" in cols
    assert cols["last_login_at"][1] == "YES"

    # Check constraint
    ck_query = text(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conname = 'ck_users_status';
        """
    )
    ck_res = await db_session.execute(ck_query)
    assert ck_res.scalar_one_or_none() == "ck_users_status"


@pytest.mark.asyncio
async def test_foreign_key_delete_rule_is_no_action_or_restrict(
    db_session: AsyncSession,
) -> None:
    """Verify that auth foreign keys do NOT use CASCADE (confirms Founder Option A)."""
    fk_query = text(
        """
        SELECT
            tc.constraint_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.referential_constraints AS rc
          ON tc.constraint_name = rc.constraint_name
        WHERE tc.table_name IN ('user_credentials', 'refresh_tokens', 'password_reset_tokens')
          AND tc.constraint_type = 'FOREIGN KEY';
        """
    )
    res = await db_session.execute(fk_query)
    rows = res.fetchall()
    assert len(rows) == 3

    for constraint_name, delete_rule in rows:
        # In PostgreSQL information_schema, default restrictive is 'NO ACTION' or 'RESTRICT'
        assert delete_rule in ("NO ACTION", "RESTRICT"), (
            f"Constraint {constraint_name} has delete_rule {delete_rule}, expected NO ACTION or RESTRICT"
        )

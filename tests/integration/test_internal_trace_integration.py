"""Integration tests for internal trace database schema, repository, and service (ORG-006)."""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationException
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrganizationMember
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.models import InternalTraceEvent
from app.modules.trace.repository import InternalTraceRepository
from app.modules.trace.service import InternalTraceService


async def _create_test_org(session: AsyncSession, name: str = "Trace Org") -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        display_name=name,
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_user(session: AsyncSession, email: str = "trace_user@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email_normalized=email,
        display_name="Trace Test User",
        status="active",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_internal_trace_table_exists(db_session: AsyncSession) -> None:
    """Verify internal_trace_events table exists in PostgreSQL."""
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'internal_trace_events';
        """
    )
    result = await db_session.execute(query)
    assert result.scalar_one_or_none() == "internal_trace_events"


@pytest.mark.asyncio
async def test_internal_trace_columns_and_nullability(db_session: AsyncSession) -> None:
    """Verify columns, data types, and nullability constraints on internal_trace_events."""
    col_query = text(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'internal_trace_events'
        ORDER BY column_name;
        """
    )
    res = await db_session.execute(col_query)
    cols = {row[0]: (row[1], row[2]) for row in res.fetchall()}

    assert cols["id"] == ("uuid", "NO")
    assert cols["organization_id"] == ("uuid", "NO")
    assert cols["actor_user_id"] == ("uuid", "YES")
    assert cols["action"] == ("character varying", "NO")
    assert cols["target_type"] == ("character varying", "YES")
    assert cols["target_id"] == ("uuid", "YES")
    assert cols["outcome"] == ("character varying", "NO")
    assert cols["request_id"] == ("character varying", "YES")
    assert cols["metadata"] == ("jsonb", "NO")
    assert cols["created_at"] == ("timestamp with time zone", "NO")
    assert "updated_at" not in cols  # Append-only schema


@pytest.mark.asyncio
async def test_internal_trace_check_constraints(db_session: AsyncSession) -> None:
    """Verify check constraints on outcome and action length."""
    ck_query = text(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'internal_trace_events'::regclass
          AND contype = 'c';
        """
    )
    res = await db_session.execute(ck_query)
    constraints = {row[0] for row in res.fetchall()}
    assert "ck_internal_trace_events_outcome" in constraints
    assert "ck_internal_trace_events_action_len" in constraints


@pytest.mark.asyncio
async def test_foreign_key_delete_rule_is_restrict_no_action(db_session: AsyncSession) -> None:
    """Verify that foreign keys do NOT use CASCADE or SET NULL (confirms FD-ORG006-01)."""
    fk_query = text(
        """
        SELECT
            tc.constraint_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.referential_constraints AS rc
          ON tc.constraint_name = rc.constraint_name
        WHERE tc.table_name = 'internal_trace_events'
          AND tc.constraint_type = 'FOREIGN KEY';
        """
    )
    res = await db_session.execute(fk_query)
    rows = res.fetchall()
    assert len(rows) == 2

    for constraint_name, delete_rule in rows:
        assert delete_rule in ("RESTRICT", "NO ACTION"), (
            f"Constraint {constraint_name} has delete_rule {delete_rule}, expected RESTRICT or NO ACTION"
        )


@pytest.mark.asyncio
async def test_internal_trace_indexes(db_session: AsyncSession) -> None:
    """Verify required indexes exist on internal_trace_events."""
    idx_query = text(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'internal_trace_events';
        """
    )
    res = await db_session.execute(idx_query)
    indexes = {row[0] for row in res.fetchall()}

    assert "ix_internal_trace_events_organization_id" in indexes
    assert "ix_internal_trace_events_org_created" in indexes
    assert "ix_internal_trace_events_request_id" in indexes


@pytest.mark.asyncio
async def test_service_records_event_with_sanitized_metadata(db_session: AsyncSession) -> None:
    """Verify service persists event with sanitized metadata within tenant scope."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session, "user1@example.com")

    service = InternalTraceService(session=db_session, organization_id=org.id)
    raw_meta = {
        "reason": "role_elevation",
        "actor_token": "secret_jwt_token",
        "target_email": "target@example.com",
    }

    event = await service.record_event(
        action=TraceAction.ORG_MEMBER_ROLE_CHANGED,
        outcome=TraceOutcome.SUCCESS,
        actor_user_id=user.id,
        target_type="organization_member",
        target_id=uuid.uuid4(),
        request_id="req-12345",
        metadata=raw_meta,
    )

    assert event.id is not None
    assert event.organization_id == org.id
    assert event.actor_user_id == user.id
    assert event.action == "org.member.role_changed"
    assert event.outcome == "success"
    assert event.request_id == "req-12345"
    assert event.event_metadata["reason"] == "role_elevation"
    assert event.event_metadata["actor_token"] == "[REDACTED]"
    assert event.event_metadata["target_email"] == "target@example.com"


@pytest.mark.asyncio
async def test_service_records_system_event_null_actor(db_session: AsyncSession) -> None:
    """Verify system-generated events with actor_user_id=None are accepted."""
    org = await _create_test_org(db_session)
    service = InternalTraceService(session=db_session, organization_id=org.id)

    event = await service.record_event(
        action=TraceAction.ORG_STATUS_CHANGED,
        outcome=TraceOutcome.SUCCESS,
        actor_user_id=None,
        metadata={"system_trigger": "maintenance_window"},
    )

    assert event.actor_user_id is None
    assert event.outcome == "success"


@pytest.mark.asyncio
async def test_tenant_isolation_reads(db_session: AsyncSession) -> None:
    """Verify Tenant A repository cannot view or list Tenant B events."""
    org_a = await _create_test_org(db_session, "Org A")
    org_b = await _create_test_org(db_session, "Org B")

    service_a = InternalTraceService(session=db_session, organization_id=org_a.id)
    service_b = InternalTraceService(session=db_session, organization_id=org_b.id)

    event_a = await service_a.record_event(
        action=TraceAction.ORG_MEMBER_INVITED,
        outcome=TraceOutcome.SUCCESS,
        metadata={"scope": "org_a"},
    )
    event_b = await service_b.record_event(
        action=TraceAction.ORG_MEMBER_INVITED,
        outcome=TraceOutcome.SUCCESS,
        metadata={"scope": "org_b"},
    )

    repo_a = InternalTraceRepository(session=db_session, organization_id=org_a.id)
    events_a = await repo_a.list_events()

    event_ids_a = {e.id for e in events_a}
    assert event_a.id in event_ids_a
    assert event_b.id not in event_ids_a

    # Cross-tenant get_by_id returns None
    fetched_cross = await repo_a.get_event_by_id(event_b.id)
    assert fetched_cross is None


@pytest.mark.asyncio
async def test_foreign_key_delete_rule_restrict_blocks_actor_user_deletion(
    db_session: AsyncSession,
) -> None:
    """Verify deleting an actor user with existing trace records is blocked (RESTRICT)."""
    org = await _create_test_org(db_session)
    user = await _create_test_user(db_session, "restrict_user@example.com")

    service = InternalTraceService(session=db_session, organization_id=org.id)
    await service.record_event(
        action=TraceAction.ORG_MEMBER_INVITED,
        outcome=TraceOutcome.SUCCESS,
        actor_user_id=user.id,
    )

    # Attempt to delete the user
    await db_session.delete(user)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_foreign_key_delete_rule_restrict_blocks_org_deletion(
    db_session: AsyncSession,
) -> None:
    """Verify deleting an organization with existing trace records is blocked (RESTRICT)."""
    org = await _create_test_org(db_session, "Delete Protected Org")
    service = InternalTraceService(session=db_session, organization_id=org.id)
    await service.record_event(
        action=TraceAction.ORG_STATUS_CHANGED,
        outcome=TraceOutcome.SUCCESS,
    )

    await db_session.delete(org)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_transaction_rollback_discards_trace_event(db_session: AsyncSession) -> None:
    """Verify that outer transaction rollback cleanly discards uncommitted trace events."""
    org = await _create_test_org(db_session)
    service = InternalTraceService(session=db_session, organization_id=org.id)

    event = await service.record_event(
        action=TraceAction.ORG_MEMBER_INVITED,
        outcome=TraceOutcome.SUCCESS,
    )
    event_id = event.id

    # Roll back transaction
    await db_session.rollback()

    # Re-query
    repo = InternalTraceRepository(session=db_session, organization_id=org.id)
    fetched = await repo.get_event_by_id(event_id)
    assert fetched is None

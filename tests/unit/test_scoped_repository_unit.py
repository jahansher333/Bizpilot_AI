"""Unit tests for ScopedRepository and tenant query invariants (ORG-005)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import BooleanClauseList, BinaryExpression
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    ScopedRepository,
    TenantScopedModel,
    validate_tenant_model,
)
from app.modules.auth.models import User
from app.modules.organizations.models import Organization, OrganizationMember


def _compile_sql(stmt) -> str:
    """Helper to compile a statement to SQL string with postgres dialect."""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_repository_binds_organization_id() -> None:
    """Repository accurately stores and exposes the bound organization_id."""
    org_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)
    repo = ScopedRepository(session=mock_session, organization_id=org_id)

    assert repo.organization_id == org_id
    assert repo.session is mock_session


def test_repository_rejects_invalid_uuid_type() -> None:
    """Repository rejects non-UUID organization_id instances at construction."""
    mock_session = MagicMock(spec=AsyncSession)
    with pytest.raises(TypeError, match="must be a valid UUID instance"):
        ScopedRepository(session=mock_session, organization_id="not-a-uuid")  # type: ignore[arg-type]


def test_repository_organization_id_immutable() -> None:
    """organization_id cannot be rebound on an existing repository instance."""
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)
    repo = ScopedRepository(session=mock_session, organization_id=org_id)

    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo.organization_id = other_org_id  # type: ignore[misc]

    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo._organization_id = other_org_id


def test_repository_session_immutable() -> None:
    """session attribute cannot be overwritten on an existing repository instance."""
    org_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)
    other_session = MagicMock(spec=AsyncSession)
    repo = ScopedRepository(session=mock_session, organization_id=org_id)

    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo.session = other_session  # type: ignore[misc]

    with pytest.raises(AttributeError, match="immutable and cannot be rebound"):
        repo._session = other_session


def test_tenant_model_validation_success() -> None:
    """OrganizationMember satisfies the tenant-owned model contract."""
    validate_tenant_model(OrganizationMember)
    assert hasattr(OrganizationMember, "id")
    assert hasattr(OrganizationMember, "organization_id")


def test_tenant_model_validation_failure_for_non_tenant_models() -> None:
    """Models lacking organization_id fail tenant-model contract validation."""
    with pytest.raises(TypeError, match="does not satisfy the tenant-owned contract"):
        validate_tenant_model(User)

    with pytest.raises(TypeError, match="does not satisfy the tenant-owned contract"):
        validate_tenant_model(Organization)


def test_scoped_query_structural_predicate() -> None:
    """scoped_query structurally injects the organization_id equality predicate."""
    org_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)
    repo = ScopedRepository(
        session=mock_session,
        organization_id=org_id,
        model_cls=OrganizationMember,
    )

    stmt = repo.scoped_query()
    sql = _compile_sql(stmt)

    assert "organization_members.organization_id" in sql
    assert str(org_id) in sql

    # Verify structural clause
    where_clause = stmt._where_criteria
    assert len(where_clause) == 1
    criterion = where_clause[0]
    assert isinstance(criterion, BinaryExpression)
    assert criterion.left.name == "organization_id"


def test_get_by_id_query_structure_and_no_for_update_by_default() -> None:
    """get_by_id structurally includes both id and organization_id, without FOR UPDATE by default."""
    org_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = ScopedRepository(
        session=mock_session,
        organization_id=org_id,
        model_cls=OrganizationMember,
    )

    import asyncio
    asyncio.run(repo.get_by_id(resource_id))

    mock_session.execute.assert_called_once()
    called_stmt = mock_session.execute.call_args[0][0]
    sql = _compile_sql(called_stmt)

    assert "organization_members.id" in sql
    assert str(resource_id) in sql
    assert "organization_members.organization_id" in sql
    assert str(org_id) in sql
    assert "FOR UPDATE" not in sql


def test_get_by_id_with_for_update() -> None:
    """get_by_id with for_update=True explicitly compiles FOR UPDATE lock."""
    org_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = ScopedRepository(
        session=mock_session,
        organization_id=org_id,
        model_cls=OrganizationMember,
    )

    import asyncio
    asyncio.run(repo.get_by_id(resource_id, for_update=True))

    called_stmt = mock_session.execute.call_args[0][0]
    sql = _compile_sql(called_stmt)

    assert "FOR UPDATE" in sql
    assert "organization_members.organization_id" in sql


def test_list_scoped_preserves_tenant_predicate_with_conditions() -> None:
    """list_scoped preserves the tenant predicate when additional conditions are applied."""
    org_id = uuid.uuid4()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    repo = ScopedRepository(
        session=mock_session,
        organization_id=org_id,
        model_cls=OrganizationMember,
    )

    import asyncio
    asyncio.run(
        repo.list_scoped(
            OrganizationMember.role == "owner",
            order_by=OrganizationMember.created_at.asc(),
            limit=10,
            offset=5,
        )
    )

    called_stmt = mock_session.execute.call_args[0][0]
    sql = _compile_sql(called_stmt)

    assert "organization_members.organization_id" in sql
    assert str(org_id) in sql
    assert "organization_members.role" in sql
    assert "LIMIT 10" in sql
    assert "OFFSET 5" in sql
    assert "ORDER BY organization_members.created_at ASC" in sql


def test_validate_tenant_relationship_structure() -> None:
    """validate_tenant_relationship builds query scoped by id and organization_id."""
    org_id = uuid.uuid4()
    related_id = uuid.uuid4()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = related_id
    mock_session.execute.return_value = mock_result

    repo = ScopedRepository(session=mock_session, organization_id=org_id)

    import asyncio
    is_valid = asyncio.run(
        repo.validate_tenant_relationship(
            related_id=related_id,
            model_cls=OrganizationMember,
        )
    )

    assert is_valid is True
    called_stmt = mock_session.execute.call_args[0][0]
    sql = _compile_sql(called_stmt)

    assert "organization_members.id" in sql
    assert str(related_id) in sql
    assert "organization_members.organization_id" in sql
    assert str(org_id) in sql


def test_validate_tenant_relationship_rejects_non_tenant_model() -> None:
    """validate_tenant_relationship raises TypeError if passed a model without organization_id."""
    org_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)
    repo = ScopedRepository(session=mock_session, organization_id=org_id)

    import asyncio
    with pytest.raises(TypeError, match="does not satisfy the tenant-owned contract"):
        asyncio.run(
            repo.validate_tenant_relationship(
                related_id=uuid.uuid4(),
                model_cls=User,
            )
        )

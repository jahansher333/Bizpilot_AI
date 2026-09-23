"""Unit tests for category schemas, models, and service logic (CAT-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.errors import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.db.repositories import TenantScopedModel, validate_tenant_model
from app.modules.categories.enums import CategoryStatus
from app.modules.categories.models import Category
from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.modules.categories.service import CategoryService


# ==============================================================================
# 1. Pydantic Schema Unit Tests
# ==============================================================================


def test_category_create_valid_trims_whitespace() -> None:
    req = CategoryCreate(name="  Beverages  ")
    assert req.name == "Beverages"


def test_category_create_name_too_short() -> None:
    with pytest.raises(ValidationError) as exc:
        CategoryCreate(name="a")
    assert "name" in str(exc.value)

    with pytest.raises(ValidationError) as exc2:
        CategoryCreate(name="   a   ")
    assert "at least 2 characters" in str(exc2.value)


def test_category_create_name_empty_or_whitespace() -> None:
    with pytest.raises(ValidationError) as exc:
        CategoryCreate(name="   ")
    assert "at least 2 characters" in str(exc.value)


def test_category_create_name_too_long() -> None:
    with pytest.raises(ValidationError) as exc:
        CategoryCreate(name="A" * 101)
    assert "name" in str(exc.value)


def test_category_create_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        CategoryCreate(name="Beverages", organization_id=uuid.uuid4())  # type: ignore[call-arg]
    assert "extra" in str(exc.value).lower()

    with pytest.raises(ValidationError) as exc2:
        CategoryCreate(name="Beverages", status="active")  # type: ignore[call-arg]
    assert "extra" in str(exc2.value).lower()


def test_category_update_valid_trims_whitespace() -> None:
    req = CategoryUpdate(name="  Cold Drinks  ")
    assert req.name == "Cold Drinks"


def test_category_update_name_validation() -> None:
    with pytest.raises(ValidationError):
        CategoryUpdate(name="x")

    with pytest.raises(ValidationError):
        CategoryUpdate(name="  ")

    with pytest.raises(ValidationError):
        CategoryUpdate(name="Y" * 101)


def test_category_update_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        CategoryUpdate(name="Cold Drinks", random_field="exploit")  # type: ignore[call-arg]
    assert "extra" in str(exc.value).lower()


def test_category_response_serialization() -> None:
    cat_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    resp = CategoryResponse(
        id=cat_id,
        organization_id=org_id,
        name="Beverages",
        status=CategoryStatus.ACTIVE.value,
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    assert resp.id == cat_id
    assert resp.organization_id == org_id
    assert resp.name == "Beverages"
    assert resp.status == "active"
    assert resp.created_by_user_id == user_id


def test_category_list_response_structure() -> None:
    resp = CategoryListResponse(
        items=[],
        total=0,
        limit=50,
        offset=0,
    )
    assert resp.items == []
    assert resp.total == 0
    assert resp.limit == 50
    assert resp.offset == 0


# ==============================================================================
# 2. Model & Protocol Unit Tests
# ==============================================================================


def test_category_model_satisfies_tenant_scoped_model() -> None:
    validate_tenant_model(Category)
    assert hasattr(Category, "id")
    assert hasattr(Category, "organization_id")
    assert hasattr(Category, "name")
    assert hasattr(Category, "status")
    assert hasattr(Category, "created_by_user_id")
    assert hasattr(Category, "created_at")
    assert hasattr(Category, "updated_at")
    assert hasattr(Category, "archived_at")


# ==============================================================================
# 3. Service Logic Unit Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_service_create_category_duplicate_active_name_conflict() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Simulate existing active category found by get_active_by_name
    existing_cat = Category(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Beverages",
        status=CategoryStatus.ACTIVE.value,
    )
    mock_repo.get_active_by_name.return_value = existing_cat

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        repository=mock_repo,
    )

    with pytest.raises(ConflictException) as exc:
        await service.create_category(CategoryCreate(name="beverages"))

    assert "already exists" in str(exc.value)
    mock_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_service_create_category_integrity_error_maps_to_conflict() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()

    mock_repo.get_active_by_name.return_value = None
    mock_repo.create.return_value = Category(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Beverages",
        status=CategoryStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Simulate race condition: DB raises unique constraint violation on flush
    mock_session.flush.side_effect = IntegrityError(
        statement="INSERT INTO categories ...",
        params={},
        orig=Exception("duplicate key value violates unique constraint uq_categories_org_active_name"),
    )

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    with pytest.raises(ConflictException) as exc:
        await service.create_category(CategoryCreate(name="Beverages"))

    assert "already exists" in str(exc.value)


@pytest.mark.asyncio
async def test_service_get_category_not_found() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()

    mock_repo.get_by_id.return_value = None

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    with pytest.raises(NotFoundException):
        await service.get_category(uuid.uuid4())


@pytest.mark.asyncio
async def test_service_update_category_on_archived_raises_conflict() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()

    archived_cat = Category(
        id=cat_id,
        organization_id=org_id,
        name="Old Drinks",
        status=CategoryStatus.ARCHIVED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_repo.get_by_id.return_value = archived_cat

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    with pytest.raises(ConflictException) as exc:
        await service.update_category(cat_id, CategoryUpdate(name="New Drinks"))

    assert "Cannot update an archived category" in str(exc.value)


@pytest.mark.asyncio
async def test_service_update_category_name_collision_raises_conflict() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    other_cat_id = uuid.uuid4()

    current_cat = Category(
        id=cat_id,
        organization_id=org_id,
        name="Old Drinks",
        status=CategoryStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    other_cat = Category(
        id=other_cat_id,
        organization_id=org_id,
        name="Snacks",
        status=CategoryStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_repo.get_by_id.return_value = current_cat
    mock_repo.get_active_by_name.return_value = other_cat

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    with pytest.raises(ConflictException) as exc:
        await service.update_category(cat_id, CategoryUpdate(name="Snacks"))

    assert "already exists" in str(exc.value)


@pytest.mark.asyncio
async def test_service_archive_category_idempotent_preserves_archived_at() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    original_archived_at = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)

    archived_cat = Category(
        id=cat_id,
        organization_id=org_id,
        name="Beverages",
        status=CategoryStatus.ARCHIVED.value,
        archived_at=original_archived_at,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_repo.get_by_id.return_value = archived_cat

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    resp = await service.archive_category(cat_id)
    assert resp.status == "archived"
    assert resp.archived_at == original_archived_at
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_service_list_categories_invalid_status_filter() -> None:
    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    org_id = uuid.uuid4()

    service = CategoryService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_repo,
    )

    with pytest.raises(ValidationException) as exc:
        await service.list_categories(status="unknown_status")

    assert "Invalid status filter" in str(exc.value)

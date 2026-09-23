"""Unit tests for product schemas, models, and service logic (CAT-002)."""

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
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.products.service import ProductService


# ==============================================================================
# 1. Pydantic Schema Unit Tests
# ==============================================================================


def test_product_create_valid_trims_whitespace() -> None:
    req = ProductCreate(
        code="  PROD-001  ",
        name="  Basmati Rice 5kg  ",
        base_unit="  bag  ",
        default_price_minor=150000,
    )
    assert req.code == "PROD-001"
    assert req.name == "Basmati Rice 5kg"
    assert req.base_unit == "bag"
    assert req.default_price_minor == 150000
    assert req.category_id is None


def test_product_create_defaults() -> None:
    req = ProductCreate(
        code="SKU-1",
        name="Plain T-Shirt",
    )
    assert req.base_unit == "piece"
    assert req.default_price_minor == 0
    assert req.category_id is None


def test_product_create_code_validation() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(code="", name="Product")

    with pytest.raises(ValidationError):
        ProductCreate(code="   ", name="Product")

    with pytest.raises(ValidationError):
        ProductCreate(code="X" * 65, name="Product")


def test_product_create_name_validation() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="a")

    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="   a   ")

    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="B" * 256)


def test_product_create_base_unit_validation() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="Product", base_unit="")

    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="Product", base_unit="   ")

    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="Product", base_unit="U" * 33)


def test_product_create_price_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-1", name="Product", default_price_minor=-1)


def test_product_create_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError) as exc:
        ProductCreate(
            code="SKU-1",
            name="Product",
            organization_id=uuid.uuid4(),  # type: ignore[call-arg]
        )
    assert "extra" in str(exc.value).lower()

    with pytest.raises(ValidationError) as exc2:
        ProductCreate(
            code="SKU-1",
            name="Product",
            status="active",  # type: ignore[call-arg]
        )
    assert "extra" in str(exc2.value).lower()

    with pytest.raises(ValidationError) as exc3:
        ProductCreate(
            code="SKU-1",
            name="Product",
            currency_code="USD",  # type: ignore[call-arg]
        )
    assert "extra" in str(exc3.value).lower()


def test_product_update_all_fields_optional() -> None:
    req = ProductUpdate()
    assert req.code is None
    assert req.name is None
    assert req.category_id is None
    assert req.base_unit is None
    assert req.default_price_minor is None
    assert len(req.model_fields_set) == 0


def test_product_update_explicit_null_category() -> None:
    req = ProductUpdate(category_id=None)
    assert "category_id" in req.model_fields_set
    assert req.category_id is None


def test_product_update_valid_trims_whitespace() -> None:
    req = ProductUpdate(
        code="  NEW-SKU  ",
        name="  Updated Name  ",
        base_unit="  kg  ",
        default_price_minor=250000,
    )
    assert req.code == "NEW-SKU"
    assert req.name == "Updated Name"
    assert req.base_unit == "kg"
    assert req.default_price_minor == 250000


def test_product_update_validation_errors() -> None:
    with pytest.raises(ValidationError):
        ProductUpdate(code="")

    with pytest.raises(ValidationError):
        ProductUpdate(name="x")

    with pytest.raises(ValidationError):
        ProductUpdate(base_unit="")

    with pytest.raises(ValidationError):
        ProductUpdate(default_price_minor=-10)

    with pytest.raises(ValidationError):
        ProductUpdate(forbidden="value")  # type: ignore[call-arg]


def test_product_response_serialization() -> None:
    prod_id = uuid.uuid4()
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    resp = ProductResponse(
        id=prod_id,
        organization_id=org_id,
        category_id=cat_id,
        code="SKU-100",
        name="Flour 10kg",
        base_unit="bag",
        default_price_minor=120000,
        currency_code="PKR",
        status="active",
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    assert resp.id == prod_id
    assert resp.code == "SKU-100"
    assert resp.category_id == cat_id
    assert resp.currency_code == "PKR"
    assert resp.default_price_minor == 120000
    assert resp.archived_at is None


def test_product_list_response() -> None:
    list_resp = ProductListResponse(
        items=[],
        total=0,
        limit=50,
        offset=0,
    )
    assert list_resp.total == 0
    assert list_resp.limit == 50
    assert list_resp.offset == 0


# ==============================================================================
# 2. Protocol & Model Compliance
# ==============================================================================


def test_product_model_satisfies_tenant_scoped_protocol() -> None:
    validate_tenant_model(Product)
    assert hasattr(Product, "id")
    assert hasattr(Product, "organization_id")
    assert hasattr(Product, "code")
    assert hasattr(Product, "name")
    assert hasattr(Product, "status")
    assert hasattr(Product, "default_price_minor")
    assert hasattr(Product, "currency_code")


# ==============================================================================
# 3. ProductService Logic Unit Tests
# ==============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_product_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_category_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_service_create_product_success(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        currency_code="PKR",
        actor_user_id=actor_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    mock_product_repo.get_active_by_code.return_value = None

    created_prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        category_id=None,
        code="PROD-01",
        name="Basmati Rice",
        base_unit="kg",
        default_price_minor=30000,
        currency_code="PKR",
        status=ProductStatus.ACTIVE.value,
        created_by_user_id=actor_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_product_repo.create.return_value = created_prod

    req = ProductCreate(
        code="  PROD-01  ",
        name="  Basmati Rice  ",
        base_unit="kg",
        default_price_minor=30000,
    )
    res = await service.create_product(req)

    assert res.code == "PROD-01"
    assert res.name == "Basmati Rice"
    assert res.currency_code == "PKR"
    mock_product_repo.get_active_by_code.assert_awaited_once_with("PROD-01")
    mock_product_repo.create.assert_awaited_once_with(
        code="PROD-01",
        name="Basmati Rice",
        category_id=None,
        base_unit="kg",
        default_price_minor=30000,
        currency_code="PKR",
        created_by_user_id=actor_id,
    )
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_create_product_active_code_collision(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    existing = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code="PROD-01",
        name="Old Item",
        status=ProductStatus.ACTIVE.value,
    )
    mock_product_repo.get_active_by_code.return_value = existing

    req = ProductCreate(code="prod-01", name="New Item")
    with pytest.raises(ConflictException) as exc:
        await service.create_product(req)
    assert "active code already exists" in str(exc.value)


@pytest.mark.asyncio
async def test_service_create_product_with_nonexistent_category(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    mock_product_repo.get_active_by_code.return_value = None
    mock_category_repo.get_by_id.return_value = None

    req = ProductCreate(code="SKU-1", name="Item", category_id=cat_id)
    with pytest.raises(NotFoundException) as exc:
        await service.create_product(req)
    assert "Category not found" in str(exc.value)


@pytest.mark.asyncio
async def test_service_create_product_with_archived_category(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    mock_product_repo.get_active_by_code.return_value = None
    archived_cat = Category(
        id=cat_id,
        organization_id=org_id,
        name="Archived Category",
        status=CategoryStatus.ARCHIVED.value,
    )
    mock_category_repo.get_by_id.return_value = archived_cat

    req = ProductCreate(code="SKU-1", name="Item", category_id=cat_id)
    with pytest.raises(ConflictException) as exc:
        await service.create_product(req)
    assert "Cannot assign an archived category" in str(exc.value)


@pytest.mark.asyncio
async def test_service_get_product_not_found(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    service = ProductService(
        session=mock_session,
        organization_id=uuid.uuid4(),
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )
    mock_product_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundException):
        await service.get_product(uuid.uuid4())


@pytest.mark.asyncio
async def test_service_list_products_invalid_status(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    service = ProductService(
        session=mock_session,
        organization_id=uuid.uuid4(),
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )
    with pytest.raises(ValidationException):
        await service.list_products(status="deleted")


@pytest.mark.asyncio
async def test_service_update_archived_product_conflict(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    archived_prod = Product(
        id=prod_id,
        organization_id=org_id,
        code="SKU-1",
        name="Archived Item",
        status=ProductStatus.ARCHIVED.value,
    )
    mock_product_repo.get_by_id.return_value = archived_prod

    with pytest.raises(ConflictException) as exc:
        await service.update_product(prod_id, ProductUpdate(name="New Name"))
    assert "Cannot update an archived product" in str(exc.value)


@pytest.mark.asyncio
async def test_service_update_product_uncategorize(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    active_prod = Product(
        id=prod_id,
        organization_id=org_id,
        category_id=cat_id,
        code="SKU-1",
        name="Item",
        base_unit="piece",
        default_price_minor=100,
        currency_code="PKR",
        status=ProductStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_product_repo.get_by_id.return_value = active_prod

    req = ProductUpdate(category_id=None)
    res = await service.update_product(prod_id, req)

    assert active_prod.category_id is None
    assert res.category_id is None
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_archive_product_idempotent(
    mock_session: AsyncMock,
    mock_product_repo: AsyncMock,
    mock_category_repo: AsyncMock,
) -> None:
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    service = ProductService(
        session=mock_session,
        organization_id=org_id,
        repository=mock_product_repo,
        category_repository=mock_category_repo,
    )

    original_archived_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    archived_prod = Product(
        id=prod_id,
        organization_id=org_id,
        code="SKU-1",
        name="Item",
        base_unit="piece",
        default_price_minor=100,
        currency_code="PKR",
        status=ProductStatus.ARCHIVED.value,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=original_archived_at,
        archived_at=original_archived_at,
    )
    mock_product_repo.get_by_id.return_value = archived_prod

    res = await service.archive_product(prod_id)

    assert res.status == ProductStatus.ARCHIVED.value
    assert res.archived_at == original_archived_at
    mock_session.flush.assert_not_called()

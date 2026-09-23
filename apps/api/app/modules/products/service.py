"""Domain service for product lifecycle management (CAT-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.categories.enums import CategoryStatus
from app.modules.categories.repository import CategoryRepository
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.products.repository import ProductRepository
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    """Domain service managing tenant-scoped product operations."""

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        currency_code: str = "PKR",
        actor_user_id: Optional[uuid.UUID] = None,
        repository: Optional[ProductRepository] = None,
        category_repository: Optional[CategoryRepository] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._currency_code = currency_code
        self._actor_user_id = actor_user_id
        self._repository = repository or ProductRepository(session, organization_id)
        self._category_repository = category_repository or CategoryRepository(session, organization_id)

    async def create_product(self, request: ProductCreate) -> ProductResponse:
        """Create a new active product in tenant with case-insensitive unique code enforcement."""
        normalized_code = request.code.strip()

        # Application-level pre-check for active code collision
        existing = await self._repository.get_active_by_code(normalized_code)
        if existing is not None:
            raise ConflictException("Product with this active code already exists in organization")

        # Validate category reference if provided
        if request.category_id is not None:
            category = await self._category_repository.get_by_id(request.category_id)
            if category is None:
                raise NotFoundException("Category not found")
            if category.status != CategoryStatus.ACTIVE.value:
                raise ConflictException("Cannot assign an archived category")

        product = await self._repository.create(
            code=normalized_code,
            name=request.name.strip(),
            category_id=request.category_id,
            base_unit=request.base_unit.strip(),
            default_price_minor=request.default_price_minor,
            currency_code=self._currency_code,
            created_by_user_id=self._actor_user_id,
        )

        try:
            await self._session.flush()
        except IntegrityError as exc:
            err_str = str(exc).lower()
            if "uq_products_org_active_code" in err_str:
                raise ConflictException(
                    "Product with this active code already exists in organization"
                ) from exc
            if "ck_products_" in err_str:
                raise ValidationException("Product validation constraint failed") from exc
            raise

        return ProductResponse.model_validate(product)

    async def get_product(self, product_id: uuid.UUID) -> ProductResponse:
        """Retrieve product by ID strictly within tenant scope."""
        product = await self._repository.get_by_id(product_id)
        if product is None:
            raise NotFoundException("Product not found")
        return ProductResponse.model_validate(product)

    async def list_products(
        self,
        status: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductListResponse:
        """List tenant products with optional status/category filter and pagination."""
        if status is not None:
            status_clean = status.strip().lower()
            if status_clean not in (ProductStatus.ACTIVE.value, ProductStatus.ARCHIVED.value):
                raise ValidationException("Invalid status filter. Must be 'active' or 'archived'")
            status = status_clean

        clamped_limit = min(max(1, limit), 100)
        clamped_offset = max(0, offset)

        items, total = await self._repository.list_products(
            status=status,
            category_id=category_id,
            limit=clamped_limit,
            offset=clamped_offset,
        )

        return ProductListResponse(
            items=[ProductResponse.model_validate(item) for item in items],
            total=total,
            limit=clamped_limit,
            offset=clamped_offset,
        )

    async def update_product(
        self,
        product_id: uuid.UUID,
        request: ProductUpdate,
    ) -> ProductResponse:
        """Update product details with active-code collision and category validation."""
        product = await self._repository.get_by_id(product_id, for_update=True)
        if product is None:
            raise NotFoundException("Product not found")

        if product.status != ProductStatus.ACTIVE.value:
            raise ConflictException("Cannot update an archived product")

        fields_set = request.model_fields_set

        if "code" in fields_set and request.code is not None:
            normalized_code = request.code.strip()
            if normalized_code.lower() != product.code.lower():
                existing = await self._repository.get_active_by_code(normalized_code)
                if existing is not None and existing.id != product.id:
                    raise ConflictException(
                        "Product with this active code already exists in organization"
                    )
            product.code = normalized_code

        if "name" in fields_set and request.name is not None:
            product.name = request.name.strip()

        if "base_unit" in fields_set and request.base_unit is not None:
            product.base_unit = request.base_unit.strip()

        if "default_price_minor" in fields_set and request.default_price_minor is not None:
            product.default_price_minor = request.default_price_minor

        if "category_id" in fields_set:
            if request.category_id is None:
                product.category_id = None
            else:
                category = await self._category_repository.get_by_id(request.category_id)
                if category is None:
                    raise NotFoundException("Category not found")
                if category.status != CategoryStatus.ACTIVE.value:
                    raise ConflictException("Cannot assign an archived category")
                product.category_id = request.category_id

        product.updated_at = datetime.now(timezone.utc)

        try:
            await self._session.flush()
        except IntegrityError as exc:
            err_str = str(exc).lower()
            if "uq_products_org_active_code" in err_str:
                raise ConflictException(
                    "Product with this active code already exists in organization"
                ) from exc
            if "ck_products_" in err_str:
                raise ValidationException("Product validation constraint failed") from exc
            raise

        return ProductResponse.model_validate(product)

    async def archive_product(self, product_id: uuid.UUID) -> ProductResponse:
        """Transition product to archived state with natural idempotency."""
        product = await self._repository.get_by_id(product_id, for_update=True)
        if product is None:
            raise NotFoundException("Product not found")

        if product.status == ProductStatus.ARCHIVED.value:
            return ProductResponse.model_validate(product)

        now = datetime.now(timezone.utc)
        product.status = ProductStatus.ARCHIVED.value
        product.archived_at = now
        product.updated_at = now

        await self._session.flush()
        return ProductResponse.model_validate(product)

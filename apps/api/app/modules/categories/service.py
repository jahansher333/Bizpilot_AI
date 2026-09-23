"""Domain service for category lifecycle management (CAT-001)."""

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
from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)


class CategoryService:
    """Domain service managing tenant-scoped category operations."""

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        repository: Optional[CategoryRepository] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._actor_user_id = actor_user_id
        self._repository = repository or CategoryRepository(session, organization_id)

    async def create_category(self, request: CategoryCreate) -> CategoryResponse:
        """Create a new active category in tenant with case-insensitive unique name enforcement."""
        normalized_name = request.name.strip()

        # Application-level pre-check
        existing = await self._repository.get_active_by_name(normalized_name)
        if existing is not None:
            raise ConflictException("Category with this active name already exists in organization")

        category = await self._repository.create(
            name=normalized_name,
            created_by_user_id=self._actor_user_id,
        )

        try:
            await self._session.flush()
        except IntegrityError as exc:
            err_str = str(exc).lower()
            if "uq_categories_org_active_name" in err_str:
                raise ConflictException(
                    "Category with this active name already exists in organization"
                ) from exc
            if "ck_categories_name_len" in err_str or "ck_categories_status" in err_str:
                raise ValidationException("Category validation constraint failed") from exc
            raise

        return CategoryResponse.model_validate(category)

    async def get_category(self, category_id: uuid.UUID) -> CategoryResponse:
        """Retrieve category by ID strictly within tenant scope."""
        category = await self._repository.get_by_id(category_id)
        if category is None:
            raise NotFoundException("Category not found")
        return CategoryResponse.model_validate(category)

    async def list_categories(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CategoryListResponse:
        """List tenant categories with optional status filter and pagination."""
        if status is not None:
            status_clean = status.strip().lower()
            if status_clean not in (CategoryStatus.ACTIVE.value, CategoryStatus.ARCHIVED.value):
                raise ValidationException("Invalid status filter. Must be 'active' or 'archived'")
            status = status_clean

        clamped_limit = min(max(1, limit), 100)
        clamped_offset = max(0, offset)

        items, total = await self._repository.list_categories(
            status=status,
            limit=clamped_limit,
            offset=clamped_offset,
        )

        return CategoryListResponse(
            items=[CategoryResponse.model_validate(item) for item in items],
            total=total,
            limit=clamped_limit,
            offset=clamped_offset,
        )

    async def update_category(
        self,
        category_id: uuid.UUID,
        request: CategoryUpdate,
    ) -> CategoryResponse:
        """Update category name with active-name collision checks."""
        category = await self._repository.get_by_id(category_id, for_update=True)
        if category is None:
            raise NotFoundException("Category not found")

        if category.status != CategoryStatus.ACTIVE.value:
            raise ConflictException("Cannot update an archived category")

        normalized_name = request.name.strip()
        if normalized_name != category.name:
            existing = await self._repository.get_active_by_name(normalized_name)
            if existing is not None and existing.id != category.id:
                raise ConflictException(
                    "Category with this active name already exists in organization"
                )

            category.name = normalized_name
            category.updated_at = datetime.now(timezone.utc)

            try:
                await self._session.flush()
            except IntegrityError as exc:
                err_str = str(exc).lower()
                if "uq_categories_org_active_name" in err_str:
                    raise ConflictException(
                        "Category with this active name already exists in organization"
                    ) from exc
                if "ck_categories_name_len" in err_str:
                    raise ValidationException("Category validation constraint failed") from exc
                raise

        return CategoryResponse.model_validate(category)

    async def archive_category(self, category_id: uuid.UUID) -> CategoryResponse:
        """Transition category to archived state."""
        category = await self._repository.get_by_id(category_id, for_update=True)
        if category is None:
            raise NotFoundException("Category not found")

        if category.status == CategoryStatus.ARCHIVED.value:
            return CategoryResponse.model_validate(category)

        now = datetime.now(timezone.utc)
        category.status = CategoryStatus.ARCHIVED.value
        category.archived_at = now
        category.updated_at = now

        await self._session.flush()
        return CategoryResponse.model_validate(category)

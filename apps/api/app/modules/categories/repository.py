"""Tenant-scoped data access repository for categories (CAT-001)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.categories.enums import CategoryStatus
from app.modules.categories.models import Category


class CategoryRepository(ScopedRepository[Category]):
    """Repository strictly scoping category queries to an organization tenant."""

    model_cls = Category

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, Category)

    async def get_active_by_name(self, name: str) -> Optional[Category]:
        """Fetch active category matching normalized name within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(
                func.lower(func.trim(Category.name)) == func.lower(func.trim(name)),
                Category.status == CategoryStatus.ACTIVE.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_categories(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Category], int]:
        """List categories within bound tenant with optional status filter and pagination."""
        base_where = [Category.organization_id == self._organization_id]
        if status is not None:
            base_where.append(Category.status == status)

        count_stmt = select(func.count(Category.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(Category)
            .where(*base_where)
            .order_by(Category.name.asc(), Category.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        items = items_res.scalars().all()

        return items, total

    async def create(
        self,
        name: str,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> Category:
        """Instantiate and stage a new active category within bound tenant."""
        category = Category(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            name=name,
            status=CategoryStatus.ACTIVE.value,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(category)
        return category

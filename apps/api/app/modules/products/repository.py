"""Tenant-scoped data access repository for products (CAT-002)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product


class ProductRepository(ScopedRepository[Product]):
    """Repository strictly scoping product queries to an organization tenant."""

    model_cls = Product

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, Product)

    async def get_active_by_code(self, code: str) -> Optional[Product]:
        """Fetch active product matching normalized code within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(
                func.lower(func.trim(Product.code)) == func.lower(func.trim(code)),
                Product.status == ProductStatus.ACTIVE.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_products(
        self,
        status: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Product], int]:
        """List products within bound tenant with optional status/category filter and pagination."""
        base_where = [Product.organization_id == self._organization_id]
        if status is not None:
            base_where.append(Product.status == status)
        if category_id is not None:
            base_where.append(Product.category_id == category_id)

        count_stmt = select(func.count(Product.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(Product)
            .where(*base_where)
            .order_by(Product.name.asc(), Product.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        items = items_res.scalars().all()

        return items, total

    async def create(
        self,
        code: str,
        name: str,
        category_id: Optional[uuid.UUID] = None,
        base_unit: str = "piece",
        default_price_minor: int = 0,
        currency_code: str = "PKR",
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> Product:
        """Instantiate and stage a new active product within bound tenant."""
        product = Product(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            category_id=category_id,
            code=code,
            name=name,
            base_unit=base_unit,
            default_price_minor=default_price_minor,
            currency_code=currency_code,
            status=ProductStatus.ACTIVE.value,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(product)
        return product

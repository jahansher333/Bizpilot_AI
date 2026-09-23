"""Tenant-scoped data access repository for inventory balances and movements (INV-001)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.inventory.enums import MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement


class InventoryRepository(ScopedRepository[InventoryBalance]):
    """Repository strictly scoping inventory queries to an organization tenant."""

    model_cls = InventoryBalance

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, InventoryBalance)

    async def get_balance_by_product_id(self, product_id: uuid.UUID) -> Optional[InventoryBalance]:
        """Fetch current balance for a product within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(InventoryBalance.product_id == product_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_balance_for_update(self, product_id: uuid.UUID) -> Optional[InventoryBalance]:
        """Fetch current balance for a product with row lock (FOR UPDATE) within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(InventoryBalance.product_id == product_id)
            .with_for_update()
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_opening_movement(self, product_id: uuid.UUID) -> bool:
        """Check if an opening movement already exists for this product in tenant."""
        stmt = (
            select(func.count(InventoryMovement.id))
            .where(
                InventoryMovement.organization_id == self._organization_id,
                InventoryMovement.product_id == product_id,
                InventoryMovement.movement_type == MovementType.OPENING.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def list_balances(
        self,
        product_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[InventoryBalance], int]:
        """List inventory balances within bound tenant with optional product filter and pagination."""
        base_where = [InventoryBalance.organization_id == self._organization_id]
        if product_id is not None:
            base_where.append(InventoryBalance.product_id == product_id)

        count_stmt = select(func.count(InventoryBalance.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(InventoryBalance)
            .where(*base_where)
            .order_by(InventoryBalance.updated_at.desc(), InventoryBalance.id.asc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        return items_res.scalars().all(), total

    async def list_movements(
        self,
        product_id: Optional[uuid.UUID] = None,
        movement_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[InventoryMovement], int]:
        """List inventory movements within bound tenant with optional filters and pagination."""
        base_where = [InventoryMovement.organization_id == self._organization_id]
        if product_id is not None:
            base_where.append(InventoryMovement.product_id == product_id)
        if movement_type is not None:
            base_where.append(InventoryMovement.movement_type == movement_type)

        count_stmt = select(func.count(InventoryMovement.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(InventoryMovement)
            .where(*base_where)
            .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.asc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        return items_res.scalars().all(), total

    async def create_balance(self, balance: InventoryBalance) -> InventoryBalance:
        """Persist a new inventory balance."""
        self._session.add(balance)
        await self._session.flush()
        return balance

    async def create_movement(self, movement: InventoryMovement) -> InventoryMovement:
        """Persist an append-only inventory movement."""
        self._session.add(movement)
        await self._session.flush()
        return movement

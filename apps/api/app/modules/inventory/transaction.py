"""Transaction and locking helpers for inventory operations (INV-003)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryBalance
from app.modules.inventory.repository import InventoryRepository


@asynccontextmanager
async def locked_inventory_scope(
    session: AsyncSession,
    organization_id: uuid.UUID,
    product_id: uuid.UUID,
) -> AsyncGenerator[Optional[InventoryBalance], None]:
    """Acquire an exclusive row lock (SELECT ... FOR UPDATE) on the inventory balance.

    Guarantees:
    - Strict tenant scoping through InventoryRepository
    - Row-level lock held until the caller's transaction completes
    - Automatic session flush before releasing scope
    """
    repo = InventoryRepository(session, organization_id)
    balance = await repo.get_balance_for_update(product_id)
    yield balance
    await session.flush()

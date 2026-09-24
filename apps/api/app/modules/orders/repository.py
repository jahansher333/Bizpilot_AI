"""Tenant-scoped data access repository for orders and items (ORD-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories import ScopedRepository
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.organizations.models import Organization


class OrderRepository(ScopedRepository[Order]):
    """Repository strictly scoping order and order item queries to an organization tenant."""

    model_cls = Order

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, Order)

    async def generate_next_order_number(self) -> str:
        """Generate a tenant-scoped deterministic next order number, e.g. ORD-0001.

        Serializes generation per organization to prevent concurrency collisions.
        """
        await self._session.execute(
            select(Organization.id)
            .where(Organization.id == self._organization_id)
            .with_for_update()
        )
        count_stmt = select(func.count(Order.id)).where(Order.organization_id == self._organization_id)
        res = await self._session.execute(count_stmt)
        count = res.scalar_one()

        # Generate candidate and verify uniqueness
        seq = count + 1
        while True:
            candidate = f"ORD-{seq:04d}"
            exists_stmt = select(Order.id).where(
                Order.organization_id == self._organization_id,
                Order.order_number == candidate,
            )
            exists_res = await self._session.execute(exists_stmt)
            if exists_res.scalar_one_or_none() is None:
                return candidate
            seq += 1


    async def get_by_order_number(self, order_number: str) -> Optional[Order]:
        """Fetch order matching order_number within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(Order.order_number == order_number)
            .options(selectinload(Order.items))
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_order_with_items(self, order_id: uuid.UUID) -> Optional[Order]:
        """Fetch order by primary key with loaded items within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_orders(
        self,
        status: Optional[str] = None,
        customer_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Order], int]:
        """List orders within bound tenant with optional filters and pagination."""
        base_where = [Order.organization_id == self._organization_id]
        if status is not None:
            base_where.append(Order.status == status)
        if customer_id is not None:
            base_where.append(Order.customer_id == customer_id)

        count_stmt = select(func.count(Order.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(Order)
            .where(*base_where)
            .options(selectinload(Order.items))
            .order_by(Order.ordered_at.desc(), Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        items = items_res.scalars().all()

        return items, total

    async def create_order(
        self,
        order_number: str,
        customer_id: Optional[uuid.UUID],
        order_total_minor: int,
        currency_code: str = "PKR",
        ordered_at: Optional[datetime] = None,
        created_by_user_id: Optional[uuid.UUID] = None,
        items_data: Optional[Sequence[dict]] = None,
    ) -> Order:
        """Create order and line items atomically in the bound tenant."""
        now = datetime.now(timezone.utc)
        order = Order(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            order_number=order_number,
            customer_id=customer_id,
            ordered_at=ordered_at or now,
            status=OrderStatus.ACTIVE.value,
            order_total_minor=order_total_minor,
            currency_code=currency_code,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(order)

        if items_data:
            for item in items_data:
                order_item = OrderItem(
                    id=uuid.uuid4(),
                    organization_id=self._organization_id,
                    order_id=order.id,
                    product_id=item.get("product_id"),
                    product_name_snapshot=item["product_name_snapshot"],
                    product_code_snapshot=item["product_code_snapshot"],
                    unit_snapshot=item["unit_snapshot"],
                    quantity=item["quantity"],
                    unit_price_minor=item["unit_price_minor"],
                    line_total_minor=item["line_total_minor"],
                    currency_code=currency_code,
                    created_at=now,
                )
                self._session.add(order_item)

        return order

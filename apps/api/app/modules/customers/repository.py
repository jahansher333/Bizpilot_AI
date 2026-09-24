"""Tenant-scoped data access repository for customers (CUS-001, CUS-002)."""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ScopedRepository
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer


class CustomerRepository(ScopedRepository[Customer]):
    """Repository strictly scoping customer queries to an organization tenant."""

    model_cls = Customer

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        super().__init__(session, organization_id, Customer)

    async def get_active_by_phone(self, phone: str) -> Optional[Customer]:
        """Fetch active customer matching phone within bound tenant."""
        stmt = (
            self.scoped_query()
            .where(
                Customer.phone == phone,
                Customer.status == CustomerStatus.ACTIVE.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_customers(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Customer], int]:
        """List customers within bound tenant with optional status/search filters and pagination."""
        base_where = [Customer.organization_id == self._organization_id]
        if status is not None:
            base_where.append(Customer.status == status)

        if search is not None and search.strip():
            term = f"%{search.strip()}%"
            base_where.append(
                or_(
                    Customer.name.ilike(term),
                    Customer.phone.ilike(term),
                )
            )

        count_stmt = select(func.count(Customer.id)).where(*base_where)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        items_stmt = (
            select(Customer)
            .where(*base_where)
            .order_by(Customer.name.asc(), Customer.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(items_stmt)
        items = items_res.scalars().all()

        return items, total

    async def create(
        self,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        notes: Optional[str] = None,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> Customer:
        """Instantiate and stage a new active customer within bound tenant."""
        customer = Customer(
            id=uuid.uuid4(),
            organization_id=self._organization_id,
            name=name,
            phone=phone,
            email=email,
            notes=notes,
            status=CustomerStatus.ACTIVE.value,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(customer)
        return customer

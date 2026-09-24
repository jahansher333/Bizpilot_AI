"""Domain service for tenant-scoped customer lifecycle (CUS-001, CUS-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import (
    CustomerCreateSchema,
    CustomerUpdateSchema,
    normalize_phone,
)


class CustomerService:
    """Encapsulates customer business logic, normalization, and tenant isolation."""

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self._session = session
        self._organization_id = organization_id
        self._repo = CustomerRepository(session, organization_id)

    async def create_customer(
        self,
        payload: CustomerCreateSchema,
        user_id: Optional[uuid.UUID] = None,
    ) -> Customer:
        """Create a new customer within the organization.

        Enforces FD-CUS001-01:
        - Active customer phone must be unique within the organization.
        - Duplicate names are allowed.
        """
        normalized_phone = normalize_phone(payload.phone)

        if normalized_phone:
            existing = await self._repo.get_active_by_phone(normalized_phone)
            if existing is not None:
                raise ConflictException("An active customer with this phone number already exists")

        customer = await self._repo.create(
            name=payload.name,
            phone=normalized_phone,
            email=payload.email,
            notes=payload.notes,
            created_by_user_id=user_id,
        )

        await self._session.commit()
        await self._session.refresh(customer)
        return customer

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        """Retrieve customer by ID within bound tenant."""
        customer = await self._repo.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        return customer

    async def update_customer(
        self,
        customer_id: uuid.UUID,
        payload: CustomerUpdateSchema,
    ) -> Customer:
        """Update customer details within bound tenant."""
        customer = await self.get_customer(customer_id)

        if customer.status == CustomerStatus.ARCHIVED.value:
            raise ValidationException("Archived customers cannot be modified")

        data = payload.model_dump(exclude_unset=True)

        if "phone" in data:
            new_phone = normalize_phone(data["phone"])
            if new_phone and new_phone != customer.phone:
                existing = await self._repo.get_active_by_phone(new_phone)
                if existing is not None and existing.id != customer.id:
                    raise ConflictException("An active customer with this phone number already exists")
            customer.phone = new_phone

        if "name" in data and data["name"] is not None:
            customer.name = data["name"]

        if "email" in data:
            customer.email = data["email"]

        if "notes" in data:
            customer.notes = data["notes"]

        customer.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(customer)
        return customer

    async def archive_customer(self, customer_id: uuid.UUID) -> Customer:
        """Archive customer. Reusable phone afterwards."""
        customer = await self.get_customer(customer_id)

        if customer.status == CustomerStatus.ARCHIVED.value:
            return customer

        customer.status = CustomerStatus.ARCHIVED.value
        customer.archived_at = datetime.now(timezone.utc)
        customer.updated_at = datetime.now(timezone.utc)

        await self._session.commit()
        await self._session.refresh(customer)
        return customer

    async def list_customers(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Customer], int]:
        """List customers with validation on status and pagination bounds."""
        if status is not None and status not in {s.value for s in CustomerStatus}:
            raise ValidationException("Invalid status filter. Must be 'active' or 'archived'")

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        return await self._repo.list_customers(
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

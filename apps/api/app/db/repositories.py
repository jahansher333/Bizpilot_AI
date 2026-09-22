"""Scoped repository base classes and query primitives (ORG-005).

Provides reusable, type-safe data access primitives that strictly bind every
tenant-owned database operation to a trusted organization scope.
"""

from __future__ import annotations

import uuid
from typing import (
    Any,
    Generic,
    Optional,
    Protocol,
    Sequence,
    Type,
    TypeVar,
    runtime_checkable,
)

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class TenantScopedModel(Protocol):
    """Protocol contract for tenant-owned SQLAlchemy models.

    Any model operating within ScopedRepository must expose both `id`
    and `organization_id` attributes.
    """

    id: Any
    organization_id: Any


T = TypeVar("T", bound=TenantScopedModel)


def validate_tenant_model(model_cls: type) -> None:
    """Validate that a model class satisfies the tenant-owned model contract."""
    if not hasattr(model_cls, "id") or not hasattr(model_cls, "organization_id"):
        raise TypeError(
            f"Model {getattr(model_cls, '__name__', str(model_cls))} does not "
            f"satisfy the tenant-owned contract (requires 'id' and 'organization_id')"
        )


class ScopedRepository(Generic[T]):
    """Base repository enforcing tenant data isolation across database operations.

    Bound at construction to:
    - AsyncSession: Active database session (transaction owned externally)
    - organization_id: Verified tenant UUID from trusted RequestContext

    The bound organization_id is immutable after initialization and cannot be rebound.
    """

    model_cls: Optional[Type[T]] = None

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        model_cls: Optional[Type[T]] = None,
    ) -> None:
        if not isinstance(organization_id, uuid.UUID):
            raise TypeError("organization_id must be a valid UUID instance")

        self._session = session
        self._organization_id = organization_id

        effective_model = model_cls or self.model_cls
        if effective_model is not None:
            validate_tenant_model(effective_model)
        self._model_cls = effective_model

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent rebinding of organization_id or session after construction."""
        if hasattr(self, "_organization_id") and name in ("_organization_id", "organization_id"):
            raise AttributeError("organization_id is immutable and cannot be rebound")
        if hasattr(self, "_session") and name in ("_session", "session"):
            raise AttributeError("session is immutable and cannot be rebound")
        super().__setattr__(name, value)

    @property
    def session(self) -> AsyncSession:
        """Access the underlying AsyncSession."""
        return self._session

    @property
    def organization_id(self) -> uuid.UUID:
        """Access the immutable, trusted organization tenant ID."""
        return self._organization_id

    def _resolve_model(self, model_cls: Optional[Type[T]] = None) -> Type[T]:
        """Resolve and validate the effective tenant model for an operation."""
        target = model_cls or self._model_cls
        if target is None:
            raise ValueError("No tenant model class specified for this repository operation")
        validate_tenant_model(target)
        return target

    def scoped_query(
        self,
        *entities: Any,
        model_cls: Optional[Type[T]] = None,
    ) -> Select:
        """Construct a SELECT statement anchored to the bound organization_id."""
        cls = self._resolve_model(model_cls)
        selection = entities if entities else (cls,)
        return select(*selection).where(cls.organization_id == self._organization_id)

    async def get_by_id(
        self,
        resource_id: uuid.UUID,
        model_cls: Optional[Type[T]] = None,
        for_update: bool = False,
    ) -> Optional[T]:
        """Fetch a single record by primary key, strictly scoped to organization."""
        cls = self._resolve_model(model_cls)
        stmt = select(cls).where(
            cls.id == resource_id,
            cls.organization_id == self._organization_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_scoped(
        self,
        *conditions: Any,
        model_cls: Optional[Type[T]] = None,
        order_by: Any = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Sequence[T]:
        """List records belonging to the bound organization matching optional conditions."""
        stmt = self.scoped_query(model_cls=model_cls)
        if conditions:
            stmt = stmt.where(*conditions)
        if order_by is not None:
            stmt = stmt.order_by(*order_by if isinstance(order_by, (list, tuple)) else [order_by])
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def exists(
        self,
        *conditions: Any,
        model_cls: Optional[Type[T]] = None,
    ) -> bool:
        """Check existence of records within the bound organization matching conditions."""
        cls = self._resolve_model(model_cls)
        stmt = select(cls.id).where(cls.organization_id == self._organization_id)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def validate_tenant_relationship(
        self,
        related_id: uuid.UUID,
        model_cls: type,
    ) -> bool:
        """Confirm that a foreign-key target belongs to the bound organization."""
        validate_tenant_model(model_cls)
        stmt = select(model_cls.id).where(
            model_cls.id == related_id,
            model_cls.organization_id == self._organization_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

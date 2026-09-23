"""Domain service for inventory balance and movement operations (INV-002, INV-003)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    AdjustmentRequest,
    CorrectionRequest,
    InventoryBalanceListResponse,
    InventoryBalanceResponse,
    InventoryMovementListResponse,
    InventoryMovementResponse,
    OpeningStockRequest,
    VoidReversalRequest,
)
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.products.repository import ProductRepository


class InventoryService:
    """Domain service managing inventory movements, adjustments, and balances.

    Enforces:
    - Same-transaction balance update and append-only movement creation
    - Negative balance prevention with row-level locking (SELECT ... FOR UPDATE)
    - Database and application invariant consistency under concurrency
    - Single opening stock per product invariant
    - Auditability through append-only movements
    """

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        actor_role: Optional[MemberRole | str] = None,
        repository: Optional[InventoryRepository] = None,
        product_repository: Optional[ProductRepository] = None,
        trace_service: Optional[Any] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._actor_user_id = actor_user_id
        self._actor_role = actor_role
        self._repository = repository or InventoryRepository(session, organization_id)
        self._product_repository = product_repository or ProductRepository(session, organization_id)

    def _check_permission(self, permission: Permission) -> None:
        """Enforce operation-level permission if actor role is bound."""
        if self._actor_role is not None:
            check_permission(self._actor_role, permission)

    def _check_void_permission(self) -> None:
        """Enforce that only Organization Owner may record void reversals."""
        if self._actor_role is not None:
            role = (
                self._actor_role
                if isinstance(self._actor_role, MemberRole)
                else MemberRole(str(self._actor_role).strip().lower())
            )
            if role != MemberRole.OWNER:
                raise AuthorizationException("Only organization owner can perform void reversals")

    def _handle_integrity_error(self, exc: IntegrityError) -> None:
        """Map database constraint violations to deterministic domain exceptions."""
        err_str = str(exc).lower()
        if "quantity_non_negative" in err_str:
            raise ValidationException("Insufficient stock on hand: balance cannot be negative") from exc
        if "org_product" in err_str or "product_id" in err_str or "inventory_balances" in err_str:
            raise ConflictException("Concurrent inventory mutation conflict for this product") from exc
        raise exc

    async def _get_active_product(self, product_id: uuid.UUID) -> Product:
        """Retrieve product and verify it is active within tenant."""
        product = await self._product_repository.get_by_id(product_id)
        if product is None:
            raise NotFoundException("Product not found")
        if product.status != ProductStatus.ACTIVE.value:
            raise ConflictException("Cannot record stock movement for archived product")
        return product

    async def get_balance(self, product_id: uuid.UUID) -> Optional[InventoryBalanceResponse]:
        """Fetch current balance for a product within bound tenant."""
        self._check_permission(Permission.INVENTORY_READ)
        balance = await self._repository.get_balance_by_product_id(product_id)
        if balance is None:
            return None
        return InventoryBalanceResponse.model_validate(balance)

    async def list_balances(
        self,
        product_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InventoryBalanceListResponse:
        """List inventory balances within bound tenant."""
        self._check_permission(Permission.INVENTORY_READ)
        items, total = await self._repository.list_balances(
            product_id=product_id,
            limit=limit,
            offset=offset,
        )
        return InventoryBalanceListResponse(
            items=[InventoryBalanceResponse.model_validate(b) for b in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def list_movements(
        self,
        product_id: Optional[uuid.UUID] = None,
        movement_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InventoryMovementListResponse:
        """List inventory movements within bound tenant."""
        self._check_permission(Permission.INVENTORY_READ)
        items, total = await self._repository.list_movements(
            product_id=product_id,
            movement_type=movement_type,
            limit=limit,
            offset=offset,
        )
        return InventoryMovementListResponse(
            items=[InventoryMovementResponse.model_validate(m) for m in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def record_opening_stock(
        self, request: OpeningStockRequest
    ) -> tuple[InventoryBalanceResponse, InventoryMovementResponse]:
        """Record initial opening stock for a product.

        Opening stock is allowed at most once per product.
        """
        self._check_permission(Permission.INVENTORY_ADJUST)
        await self._get_active_product(request.product_id)

        has_opening = await self._repository.has_opening_movement(request.product_id)
        if has_opening:
            raise ConflictException("Opening stock has already been recorded for this product")

        # Row-lock balance if it exists
        balance = await self._repository.get_balance_for_update(request.product_id)
        if balance is not None and balance.on_hand_quantity > 0:
            raise ConflictException("Opening stock has already been recorded for this product")

        now = datetime.now(timezone.utc)
        try:
            if balance is None:
                balance = InventoryBalance(
                    id=uuid.uuid4(),
                    organization_id=self._organization_id,
                    product_id=request.product_id,
                    on_hand_quantity=request.quantity,
                    version=1,
                    updated_at=now,
                )
                await self._repository.create_balance(balance)
            else:
                balance.on_hand_quantity = request.quantity
                balance.version += 1
                balance.updated_at = now

            reason_str = request.reason.strip() if request.reason and request.reason.strip() else "Opening stock"
            movement = InventoryMovement(
                id=uuid.uuid4(),
                organization_id=self._organization_id,
                product_id=request.product_id,
                movement_type=MovementType.OPENING.value,
                quantity_delta=request.quantity,
                source_type=MovementSourceType.OPENING.value,
                source_id=None,
                reason=reason_str,
                created_by_user_id=self._actor_user_id,
                created_at=now,
            )
            await self._repository.create_movement(movement)
            await self._session.flush()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)

        return (
            InventoryBalanceResponse.model_validate(balance),
            InventoryMovementResponse.model_validate(movement),
        )

    async def record_adjustment(
        self, request: AdjustmentRequest
    ) -> tuple[InventoryBalanceResponse, InventoryMovementResponse]:
        """Record a manual inventory adjustment with required reason."""
        self._check_permission(Permission.INVENTORY_ADJUST)
        await self._get_active_product(request.product_id)

        reason_str = request.reason.strip()
        if len(reason_str) < 3:
            raise ValidationException("Reason is required for manual adjustments (minimum 3 characters)")

        # Row-lock balance
        balance = await self._repository.get_balance_for_update(request.product_id)
        current_qty = balance.on_hand_quantity if balance is not None else 0
        new_qty = current_qty + request.quantity_delta

        if new_qty < 0:
            raise ValidationException(
                f"Insufficient stock on hand: current balance is {current_qty}, adjustment delta is {request.quantity_delta}"
            )

        now = datetime.now(timezone.utc)
        try:
            if balance is None:
                balance = InventoryBalance(
                    id=uuid.uuid4(),
                    organization_id=self._organization_id,
                    product_id=request.product_id,
                    on_hand_quantity=new_qty,
                    version=1,
                    updated_at=now,
                )
                await self._repository.create_balance(balance)
            else:
                balance.on_hand_quantity = new_qty
                balance.version += 1
                balance.updated_at = now

            movement = InventoryMovement(
                id=uuid.uuid4(),
                organization_id=self._organization_id,
                product_id=request.product_id,
                movement_type=MovementType.ADJUSTMENT.value,
                quantity_delta=request.quantity_delta,
                source_type=MovementSourceType.ADJUSTMENT.value,
                source_id=None,
                reason=reason_str,
                created_by_user_id=self._actor_user_id,
                created_at=now,
            )
            await self._repository.create_movement(movement)
            await self._session.flush()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)

        return (
            InventoryBalanceResponse.model_validate(balance),
            InventoryMovementResponse.model_validate(movement),
        )

    async def record_correction(
        self, request: CorrectionRequest
    ) -> tuple[InventoryBalanceResponse, InventoryMovementResponse]:
        """Record an inventory correction with required reason."""
        self._check_permission(Permission.INVENTORY_ADJUST)
        await self._get_active_product(request.product_id)

        reason_str = request.reason.strip()
        if len(reason_str) < 3:
            raise ValidationException("Reason is required for inventory corrections (minimum 3 characters)")

        # Row-lock balance
        balance = await self._repository.get_balance_for_update(request.product_id)
        current_qty = balance.on_hand_quantity if balance is not None else 0
        new_qty = current_qty + request.quantity_delta

        if new_qty < 0:
            raise ValidationException(
                f"Insufficient stock on hand: current balance is {current_qty}, correction delta is {request.quantity_delta}"
            )

        now = datetime.now(timezone.utc)
        try:
            if balance is None:
                balance = InventoryBalance(
                    id=uuid.uuid4(),
                    organization_id=self._organization_id,
                    product_id=request.product_id,
                    on_hand_quantity=new_qty,
                    version=1,
                    updated_at=now,
                )
                await self._repository.create_balance(balance)
            else:
                balance.on_hand_quantity = new_qty
                balance.version += 1
                balance.updated_at = now

            movement = InventoryMovement(
                id=uuid.uuid4(),
                organization_id=self._organization_id,
                product_id=request.product_id,
                movement_type=MovementType.CORRECTION.value,
                quantity_delta=request.quantity_delta,
                source_type=MovementSourceType.CORRECTION.value,
                source_id=None,
                reason=reason_str,
                created_by_user_id=self._actor_user_id,
                created_at=now,
            )
            await self._repository.create_movement(movement)
            await self._session.flush()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)

        return (
            InventoryBalanceResponse.model_validate(balance),
            InventoryMovementResponse.model_validate(movement),
        )

    async def record_void_reversal(
        self, request: VoidReversalRequest
    ) -> tuple[InventoryBalanceResponse, InventoryMovementResponse]:
        """Record an inventory void reversal, strictly authorized to Owner."""
        self._check_void_permission()
        await self._get_active_product(request.product_id)

        reason_str = request.reason.strip() if request.reason and request.reason.strip() else "Void reversal"

        # Row-lock balance
        balance = await self._repository.get_balance_for_update(request.product_id)
        current_qty = balance.on_hand_quantity if balance is not None else 0
        new_qty = current_qty + request.quantity_delta

        if new_qty < 0:
            raise ValidationException(
                f"Insufficient stock on hand: current balance is {current_qty}, reversal delta is {request.quantity_delta}"
            )

        now = datetime.now(timezone.utc)
        try:
            if balance is None:
                balance = InventoryBalance(
                    id=uuid.uuid4(),
                    organization_id=self._organization_id,
                    product_id=request.product_id,
                    on_hand_quantity=new_qty,
                    version=1,
                    updated_at=now,
                )
                await self._repository.create_balance(balance)
            else:
                balance.on_hand_quantity = new_qty
                balance.version += 1
                balance.updated_at = now

            movement = InventoryMovement(
                id=uuid.uuid4(),
                organization_id=self._organization_id,
                product_id=request.product_id,
                movement_type=MovementType.VOID_REVERSAL.value,
                quantity_delta=request.quantity_delta,
                source_type=MovementSourceType.VOID_REVERSAL.value,
                source_id=request.source_id,
                reason=reason_str,
                created_by_user_id=self._actor_user_id,
                created_at=now,
            )
            await self._repository.create_movement(movement)
            await self._session.flush()
        except IntegrityError as exc:
            self._handle_integrity_error(exc)

        return (
            InventoryBalanceResponse.model_validate(balance),
            InventoryMovementResponse.model_validate(movement),
        )

"""Domain service for atomic order creation and inventory updates (ORD-003)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.repository import CustomerRepository
from app.modules.idempotency.service import IdempotencyService, compute_request_hash
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.orders.calculator import OrderCalculator
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    OrderCorrectRequestSchema,
    OrderCreateSchema,
    OrderItemResponseSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
    OrderVoidRequestSchema,
)
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.products.repository import ProductRepository
from app.modules.trace.enums import TraceAction, TraceOutcome
from app.modules.trace.service import InternalTraceService


class OrderService:
    """Domain service managing atomic order transactions, inventory decrement, void, and correction."""

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        actor_role: Optional[MemberRole | str] = None,
        repository: Optional[OrderRepository] = None,
        inventory_repository: Optional[InventoryRepository] = None,
        product_repository: Optional[ProductRepository] = None,
        customer_repository: Optional[CustomerRepository] = None,
        idempotency_service: Optional[IdempotencyService] = None,
        trace_service: Optional[InternalTraceService] = None,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._actor_user_id = actor_user_id
        self._actor_role = actor_role
        self._repository = repository or OrderRepository(session, organization_id)
        self._inventory_repository = inventory_repository or InventoryRepository(session, organization_id)
        self._product_repository = product_repository or ProductRepository(session, organization_id)
        self._customer_repository = customer_repository or CustomerRepository(session, organization_id)
        self._idempotency_service = idempotency_service or IdempotencyService(session)
        self._trace_service = trace_service or InternalTraceService(session, organization_id)


    def _check_permission(self, permission: Permission) -> None:
        """Enforce operation-level permission if actor role is bound."""
        if self._actor_role is not None:
            check_permission(self._actor_role, permission)

    def _handle_integrity_error(self, exc: IntegrityError) -> None:
        """Map database constraint violations to deterministic domain exceptions."""
        err_str = str(exc).lower()
        if "quantity_non_negative" in err_str:
            raise ValidationException("Insufficient stock on hand: balance cannot be negative") from exc
        if "uq_orders_org_order_number" in err_str:
            raise ConflictException("Duplicate order number conflict") from exc
        if "uq_idempotency_keys_org_user_op_key" in err_str:
            raise ConflictException("Concurrent request with the same idempotency key in progress") from exc
        raise exc


    async def get_order(self, order_id: uuid.UUID) -> OrderResponseSchema:
        """Retrieve a specific order by ID with loaded line items."""
        self._check_permission(Permission.ORDERS_READ)
        order = await self._repository.get_order_with_items(order_id)
        if order is None:
            raise NotFoundException("Order not found")
        return OrderResponseSchema.model_validate(order)

    async def list_orders(
        self,
        status: Optional[str] = None,
        customer_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> OrderListResponseSchema:
        """List orders for the bound tenant with pagination and optional filters."""
        self._check_permission(Permission.ORDERS_READ)
        orders, total = await self._repository.list_orders(
            status=status,
            customer_id=customer_id,
            limit=limit,
            offset=offset,
        )
        return OrderListResponseSchema(
            items=[OrderResponseSchema.model_validate(o) for o in orders],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create_order(
        self,
        data: OrderCreateSchema,
        idempotency_key: Optional[str] = None,
        idempotency_expires_at: Optional[datetime] = None,
    ) -> OrderResponseSchema:
        """Atomically validate stock, decrement inventory balances, record movements, and create order.

        Supports optional idempotency key to prevent duplicate sales and stock deductions upon retry.
        """
        self._check_permission(Permission.ORDERS_CREATE)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            if self._actor_user_id is None:
                raise ValidationException("Actor user ID is required when using an idempotency key")
            req_hash = compute_request_hash(data)
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=self._actor_user_id,
                operation="order:create",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                return OrderResponseSchema.model_validate_json(payload_str)

        if not data.items:
            raise ValidationException("Order must contain at least one line item")

        # 1. Deterministic calculation using integer arithmetic
        calc_result = OrderCalculator.calculate_order(data.items, currency_code=data.currency_code)

        # 2. Customer validation (if specified)
        if data.customer_id is not None:
            customer = await self._customer_repository.get_by_id(data.customer_id)
            if customer is None:
                raise NotFoundException("Customer not found")
            if customer.status != CustomerStatus.ACTIVE.value:
                raise ConflictException("Cannot create order for archived customer")

        # 3. Aggregate requested quantities per product to handle multi-line order of same product
        demanded_by_product: dict[uuid.UUID, int] = defaultdict(int)
        for item in data.items:
            demanded_by_product[item.product_id] += item.quantity

        # 4. Deterministic locking order (sorted by product_id UUID) to avoid deadlocks
        sorted_product_ids = sorted(demanded_by_product.keys())

        now = datetime.now(timezone.utc)
        order_id = uuid.uuid4()
        order_number = await self._repository.generate_next_order_number()

        try:
            async with self._session.begin_nested():
                # First pass: lock all balances and validate active products and stock
                locked_balances: dict[uuid.UUID, InventoryBalance] = {}
                active_products: dict[uuid.UUID, Product] = {}

                for pid in sorted_product_ids:
                    product = await self._product_repository.get_by_id(pid)
                    if product is None:
                        raise NotFoundException(f"Product '{pid}' not found")
                    if product.status != ProductStatus.ACTIVE.value:
                        raise ConflictException(f"Cannot order archived product '{product.name}'")
                    active_products[pid] = product

                    balance = await self._inventory_repository.get_balance_for_update(pid)
                    demanded_qty = demanded_by_product[pid]
                    available = balance.on_hand_quantity if balance else 0
                    if balance is None or available < demanded_qty:
                        raise ValidationException(
                            f"Insufficient stock for product '{product.name}'. Available: {available}, Requested: {demanded_qty}"
                        )
                    locked_balances[pid] = balance

                # Second pass: apply inventory deductions and record append-only movements
                for pid in sorted_product_ids:
                    demanded_qty = demanded_by_product[pid]
                    balance = locked_balances[pid]
                    balance.on_hand_quantity -= demanded_qty
                    balance.version += 1
                    balance.updated_at = now

                    movement = InventoryMovement(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        product_id=pid,
                        movement_type=MovementType.SALE.value,
                        quantity_delta=-demanded_qty,
                        source_type=MovementSourceType.ORDER.value,
                        source_id=order_id,
                        reason=f"order_sale:{order_number}",
                        created_by_user_id=self._actor_user_id,
                        created_at=now,
                    )
                    self._session.add(movement)

                # 5. Create Order and OrderItems
                order = Order(
                    id=order_id,
                    organization_id=self._organization_id,
                    order_number=order_number,
                    customer_id=data.customer_id,
                    ordered_at=data.ordered_at or now,
                    status=OrderStatus.ACTIVE.value,
                    order_total_minor=calc_result.order_total_minor,
                    currency_code=calc_result.currency_code,
                    created_by_user_id=self._actor_user_id,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(order)

                # Map calculated items with snapshots
                for item in data.items:
                    product = active_products[item.product_id]
                    line_total = OrderCalculator.calculate_line_total(item.quantity, item.unit_price_minor)
                    order_item = OrderItem(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        order_id=order_id,
                        product_id=product.id,
                        product_name_snapshot=product.name,
                        product_code_snapshot=product.code,
                        unit_snapshot=product.base_unit,
                        quantity=item.quantity,
                        unit_price_minor=item.unit_price_minor,
                        line_total_minor=line_total,
                        currency_code=calc_result.currency_code,
                        created_at=now,
                    )
                    self._session.add(order_item)

                await self._session.flush()

                # Reload full order with items inside savepoint
                created_order = await self._repository.get_order_with_items(order_id)
                order_response = OrderResponseSchema.model_validate(created_order)

                # Atomically persist idempotency response record if requested
                if clean_key and req_hash and self._actor_user_id:
                    await self._idempotency_service.record_response(
                        organization_id=self._organization_id,
                        user_id=self._actor_user_id,
                        operation="order:create",
                        idempotency_key=clean_key,
                        request_hash=req_hash,
                        response_code=201,
                        response_payload=order_response.model_dump_json(),
                        expires_at=idempotency_expires_at,
                    )
                    await self._session.flush()

            return order_response

        except IntegrityError as exc:
            self._handle_integrity_error(exc)
            raise

    async def void_order(
        self,
        order_id: uuid.UUID,
        request: OrderVoidRequestSchema,
        idempotency_key: Optional[str] = None,
    ) -> OrderResponseSchema:
        """Void an existing active order and restore inventory balances via append-only movements.

        Enforces:
        - Permission: Owner only (Permission.ORDERS_VOID)
        - Order must exist in tenant and have status == OrderStatus.ACTIVE
        - Append-only reversal movements (MovementType.VOID_REVERSAL, positive delta)
        - Emits internal trace event: TraceAction.FINANCE_RECORD_VOIDED
        - Preserves immutable history: order and items are NOT deleted
        - Optional idempotency support
        """
        self._check_permission(Permission.ORDERS_VOID)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            if self._actor_user_id is None:
                raise ValidationException("Actor user ID is required when using an idempotency key")
            req_hash = compute_request_hash({"order_id": str(order_id), "reason": request.reason})
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=self._actor_user_id,
                operation="order:void",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                return OrderResponseSchema.model_validate_json(payload_str)

        reason_str = request.reason.strip()
        if len(reason_str) < 3:
            raise ValidationException("Reason must be at least 3 characters")

        order = await self._repository.get_order_with_items(order_id)
        if order is None:
            raise NotFoundException("Order not found")

        if order.status == OrderStatus.VOIDED.value:
            raise ConflictException("Order is already voided")
        if order.status == OrderStatus.CORRECTED.value:
            raise ConflictException("Cannot void an order that has already been corrected")
        if order.status != OrderStatus.ACTIVE.value:
            raise ConflictException(f"Cannot void order with status '{order.status}'")

        # Aggregate item quantities to reverse
        demanded_by_product: dict[uuid.UUID, int] = defaultdict(int)
        for item in order.items:
            if item.product_id is not None:
                demanded_by_product[item.product_id] += item.quantity

        sorted_product_ids = sorted(demanded_by_product.keys())
        now = datetime.now(timezone.utc)

        try:
            async with self._session.begin_nested():
                # Lock balances and restore quantities
                for pid in sorted_product_ids:
                    restore_qty = demanded_by_product[pid]
                    balance = await self._inventory_repository.get_balance_for_update(pid)
                    if balance is None:
                        balance = InventoryBalance(
                            id=uuid.uuid4(),
                            organization_id=self._organization_id,
                            product_id=pid,
                            on_hand_quantity=restore_qty,
                            version=1,
                            updated_at=now,
                        )
                        self._session.add(balance)
                    else:
                        balance.on_hand_quantity += restore_qty
                        balance.version += 1
                        balance.updated_at = now

                    # Append-only reversal movement
                    movement = InventoryMovement(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        product_id=pid,
                        movement_type=MovementType.VOID_REVERSAL.value,
                        quantity_delta=restore_qty,
                        source_type=MovementSourceType.ORDER.value,
                        source_id=order.id,
                        reason=f"order_void:{reason_str}",
                        created_by_user_id=self._actor_user_id,
                        created_at=now,
                    )
                    self._session.add(movement)

                # Update order status
                order.status = OrderStatus.VOIDED.value
                order.voided_at = now
                order.updated_at = now

                # Emit internal trace event
                await self._trace_service.record_event(
                    action=TraceAction.FINANCE_RECORD_VOIDED,
                    outcome=TraceOutcome.SUCCESS,
                    actor_user_id=self._actor_user_id,
                    target_type="order",
                    target_id=order.id,
                    metadata={"order_number": order.order_number, "reason": reason_str},
                )

                await self._session.flush()

                # Refresh order with items
                updated_order = await self._repository.get_order_with_items(order_id)
                order_response = OrderResponseSchema.model_validate(updated_order)

                if clean_key and req_hash and self._actor_user_id:
                    await self._idempotency_service.record_response(
                        organization_id=self._organization_id,
                        user_id=self._actor_user_id,
                        operation="order:void",
                        idempotency_key=clean_key,
                        request_hash=req_hash,
                        response_code=200,
                        response_payload=order_response.model_dump_json(),
                    )
                    await self._session.flush()

            return order_response

        except IntegrityError as exc:
            self._handle_integrity_error(exc)
            raise

    async def correct_order(
        self,
        order_id: uuid.UUID,
        request: OrderCorrectRequestSchema,
        idempotency_key: Optional[str] = None,
    ) -> OrderResponseSchema:
        """Correct an active order by creating a replacement order and linking them.

        Enforces:
        - Permission: Owner or Manager (Permission.ORDERS_CORRECT)
        - Original order must exist and be ACTIVE
        - Original stock restored via CORRECTION movements
        - Replacement order stock validated and deducted via SALE movements
        - Original order status updated to CORRECTED, replaced_by_order_id set
        - Replacement order corrects_order_id set to original_order.id
        - Emits internal trace event: TraceAction.FINANCE_RECORD_CORRECTED
        - Preserves immutable history: original order and items are NOT deleted
        - Optional idempotency support
        """
        self._check_permission(Permission.ORDERS_CORRECT)

        clean_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        req_hash = None
        if clean_key:
            if self._actor_user_id is None:
                raise ValidationException("Actor user ID is required when using an idempotency key")
            req_hash = compute_request_hash({"order_id": str(order_id), "payload": request.model_dump()})
            cached = await self._idempotency_service.get_stored_response(
                organization_id=self._organization_id,
                user_id=self._actor_user_id,
                operation="order:correct",
                idempotency_key=clean_key,
                request_hash=req_hash,
            )
            if cached is not None:
                _, payload_str = cached
                return OrderResponseSchema.model_validate_json(payload_str)

        reason_str = request.reason.strip()
        if len(reason_str) < 3:
            raise ValidationException("Reason must be at least 3 characters")

        if not request.items:
            raise ValidationException("Replacement order must contain at least one line item")

        original_order = await self._repository.get_order_with_items(order_id)
        if original_order is None:
            raise NotFoundException("Order not found")

        if original_order.status == OrderStatus.VOIDED.value:
            raise ConflictException("Cannot correct a voided order")
        if original_order.status == OrderStatus.CORRECTED.value:
            raise ConflictException("Order is already corrected")
        if original_order.status != OrderStatus.ACTIVE.value:
            raise ConflictException(f"Cannot correct order with status '{original_order.status}'")

        # 1. Calculate replacement order financial totals
        calc_result = OrderCalculator.calculate_order(request.items, currency_code=request.currency_code)

        # 2. Validate customer if specified
        target_customer_id = request.customer_id if request.customer_id is not None else original_order.customer_id
        if target_customer_id is not None:
            customer = await self._customer_repository.get_by_id(target_customer_id)
            if customer is None:
                raise NotFoundException("Customer not found")
            if customer.status != CustomerStatus.ACTIVE.value:
                raise ConflictException("Cannot create order for archived customer")

        # 3. Analyze stock impacts:
        # Reversal of original order quantities
        orig_qty_by_prod: dict[uuid.UUID, int] = defaultdict(int)
        for item in original_order.items:
            if item.product_id is not None:
                orig_qty_by_prod[item.product_id] += item.quantity

        # New demand for replacement order
        new_qty_by_prod: dict[uuid.UUID, int] = defaultdict(int)
        for item in request.items:
            new_qty_by_prod[item.product_id] += item.quantity

        # Deterministic locking of ALL involved product IDs in sorted order
        all_involved_pids = sorted(set(orig_qty_by_prod.keys()) | set(new_qty_by_prod.keys()))

        now = datetime.now(timezone.utc)
        replacement_order_id = uuid.uuid4()
        replacement_order_number = await self._repository.generate_next_order_number()

        try:
            async with self._session.begin_nested():
                locked_balances: dict[uuid.UUID, InventoryBalance] = {}
                replacement_products: dict[uuid.UUID, Product] = {}

                # Lock all balances in deterministic order
                for pid in all_involved_pids:
                    balance = await self._inventory_repository.get_balance_for_update(pid)
                    if balance is None:
                        balance = InventoryBalance(
                            id=uuid.uuid4(),
                            organization_id=self._organization_id,
                            product_id=pid,
                            on_hand_quantity=0,
                            version=1,
                            updated_at=now,
                        )
                        self._session.add(balance)
                    locked_balances[pid] = balance

                # Validate new products are active
                for pid in sorted(new_qty_by_prod.keys()):
                    product = await self._product_repository.get_by_id(pid)
                    if product is None:
                        raise NotFoundException(f"Product '{pid}' not found")
                    if product.status != ProductStatus.ACTIVE.value:
                        raise ConflictException(f"Cannot order archived product '{product.name}'")
                    replacement_products[pid] = product

                # Step A: Restore original quantities with CORRECTION movements
                for pid in sorted(orig_qty_by_prod.keys()):
                    restored_qty = orig_qty_by_prod[pid]
                    balance = locked_balances[pid]
                    balance.on_hand_quantity += restored_qty
                    balance.version += 1
                    balance.updated_at = now

                    rev_movement = InventoryMovement(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        product_id=pid,
                        movement_type=MovementType.CORRECTION.value,
                        quantity_delta=restored_qty,
                        source_type=MovementSourceType.ORDER.value,
                        source_id=original_order.id,
                        reason=f"order_correction_reversal:{reason_str}",
                        created_by_user_id=self._actor_user_id,
                        created_at=now,
                    )
                    self._session.add(rev_movement)

                # Step B: Check sufficient stock and deduct new quantities with SALE movements
                for pid in sorted(new_qty_by_prod.keys()):
                    demanded_qty = new_qty_by_prod[pid]
                    balance = locked_balances[pid]
                    if balance.on_hand_quantity < demanded_qty:
                        prod = replacement_products[pid]
                        raise ValidationException(
                            f"Insufficient stock for product '{prod.name}'. Available: {balance.on_hand_quantity}, Requested: {demanded_qty}"
                        )
                    balance.on_hand_quantity -= demanded_qty
                    balance.version += 1
                    balance.updated_at = now

                    sale_movement = InventoryMovement(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        product_id=pid,
                        movement_type=MovementType.SALE.value,
                        quantity_delta=-demanded_qty,
                        source_type=MovementSourceType.ORDER.value,
                        source_id=replacement_order_id,
                        reason=f"order_sale:{replacement_order_number}",
                        created_by_user_id=self._actor_user_id,
                        created_at=now,
                    )
                    self._session.add(sale_movement)

                # Step C: Create replacement order
                replacement_order = Order(
                    id=replacement_order_id,
                    organization_id=self._organization_id,
                    order_number=replacement_order_number,
                    customer_id=target_customer_id,
                    ordered_at=request.ordered_at or now,
                    status=OrderStatus.ACTIVE.value,
                    order_total_minor=calc_result.order_total_minor,
                    currency_code=calc_result.currency_code,
                    created_by_user_id=self._actor_user_id,
                    corrects_order_id=original_order.id,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(replacement_order)

                for item in request.items:
                    product = replacement_products[item.product_id]
                    line_total = OrderCalculator.calculate_line_total(item.quantity, item.unit_price_minor)
                    order_item = OrderItem(
                        id=uuid.uuid4(),
                        organization_id=self._organization_id,
                        order_id=replacement_order_id,
                        product_id=product.id,
                        product_name_snapshot=product.name,
                        product_code_snapshot=product.code,
                        unit_snapshot=product.base_unit,
                        quantity=item.quantity,
                        unit_price_minor=item.unit_price_minor,
                        line_total_minor=line_total,
                        currency_code=calc_result.currency_code,
                        created_at=now,
                    )
                    self._session.add(order_item)

                # Flush to persist replacement order before linking foreign key from original order
                await self._session.flush()

                # Step D: Update original order links and status
                original_order.status = OrderStatus.CORRECTED.value
                original_order.replaced_by_order_id = replacement_order_id
                original_order.updated_at = now

                # Step E: Emit trace event
                await self._trace_service.record_event(
                    action=TraceAction.FINANCE_RECORD_CORRECTED,
                    outcome=TraceOutcome.SUCCESS,
                    actor_user_id=self._actor_user_id,
                    target_type="order",
                    target_id=original_order.id,
                    metadata={
                        "original_order_number": original_order.order_number,
                        "replacement_order_number": replacement_order_number,
                        "reason": reason_str,
                    },
                )

                await self._session.flush()

                # Reload full replacement order with items
                created_rep_order = await self._repository.get_order_with_items(replacement_order_id)
                order_response = OrderResponseSchema.model_validate(created_rep_order)

                if clean_key and req_hash and self._actor_user_id:
                    await self._idempotency_service.record_response(
                        organization_id=self._organization_id,
                        user_id=self._actor_user_id,
                        operation="order:correct",
                        idempotency_key=clean_key,
                        request_hash=req_hash,
                        response_code=200,
                        response_payload=order_response.model_dump_json(),
                    )
                    await self._session.flush()

            return order_response

        except IntegrityError as exc:
            self._handle_integrity_error(exc)
            raise

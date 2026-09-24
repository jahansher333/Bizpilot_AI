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
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.orders.calculator import OrderCalculator
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    OrderCreateSchema,
    OrderItemResponseSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
)
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import Permission, check_permission
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.products.repository import ProductRepository


class OrderService:
    """Domain service managing atomic order transactions and inventory decrement."""

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
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._actor_user_id = actor_user_id
        self._actor_role = actor_role
        self._repository = repository or OrderRepository(session, organization_id)
        self._inventory_repository = inventory_repository or InventoryRepository(session, organization_id)
        self._product_repository = product_repository or ProductRepository(session, organization_id)
        self._customer_repository = customer_repository or CustomerRepository(session, organization_id)

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

    async def create_order(self, data: OrderCreateSchema) -> OrderResponseSchema:
        """Atomically validate stock, decrement inventory balances, record movements, and create order."""
        self._check_permission(Permission.ORDERS_CREATE)

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

            # Reload full order with items
            created_order = await self._repository.get_order_with_items(order_id)
            return OrderResponseSchema.model_validate(created_order)

        except IntegrityError as exc:
            self._handle_integrity_error(exc)
            raise


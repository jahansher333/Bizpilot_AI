"""Unit tests for OrderService atomic business logic and invariant validation (ORD-003)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import OrderCreateSchema, OrderItemCreateSchema
from app.modules.orders.service import OrderService
from app.modules.organizations.enums import MemberRole
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = None
    nested_cm.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_cm)
    return session



@pytest.fixture
def mock_order_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.generate_next_order_number = AsyncMock(return_value="ORD-0001")
    return repo


@pytest.fixture
def mock_inv_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_prod_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_cust_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def active_product(org_id: uuid.UUID) -> Product:
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code="SKU-001",
        name="Basmati Rice 5kg",
        base_unit="bag",
        default_price_minor=120000,
        currency_code="PKR",
        status=ProductStatus.ACTIVE.value,
    )
    return prod


@pytest.fixture
def active_customer(org_id: uuid.UUID) -> Customer:
    cust = Customer(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Muhammad Tariq",
        phone="03001234567",
        status=CustomerStatus.ACTIVE.value,
    )
    return cust


@pytest.mark.asyncio
async def test_order_creation_success(
    mock_session: AsyncMock,
    mock_order_repo: AsyncMock,
    mock_inv_repo: AsyncMock,
    mock_prod_repo: AsyncMock,
    mock_cust_repo: AsyncMock,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    active_product: Product,
    active_customer: Customer,
) -> None:
    service = OrderService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
        repository=mock_order_repo,
        inventory_repository=mock_inv_repo,
        product_repository=mock_prod_repo,
        customer_repository=mock_cust_repo,
    )

    mock_cust_repo.get_by_id.return_value = active_customer
    mock_prod_repo.get_by_id.return_value = active_product

    balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=active_product.id,
        on_hand_quantity=50,
        version=1,
    )
    mock_inv_repo.get_balance_for_update.return_value = balance

    now = datetime.now(timezone.utc)
    created_order = Order(
        id=uuid.uuid4(),
        organization_id=org_id,
        order_number="ORD-0001",
        customer_id=active_customer.id,
        ordered_at=now,
        status=OrderStatus.ACTIVE.value,
        order_total_minor=240000,
        currency_code="PKR",
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    order_item = OrderItem(
        id=uuid.uuid4(),
        organization_id=org_id,
        order_id=created_order.id,
        product_id=active_product.id,
        product_name_snapshot="Basmati Rice 5kg",
        product_code_snapshot="SKU-001",
        unit_snapshot="bag",
        quantity=2,
        unit_price_minor=120000,
        line_total_minor=240000,
        currency_code="PKR",
        created_at=now,
    )
    created_order.items = [order_item]
    mock_order_repo.get_order_with_items.return_value = created_order

    req = OrderCreateSchema(
        customer_id=active_customer.id,
        items=[
            OrderItemCreateSchema(
                product_id=active_product.id,
                quantity=2,
                unit_price_minor=120000,
            )
        ],
    )

    result = await service.create_order(req)

    assert result.order_number == "ORD-0001"
    assert result.order_total_minor == 240000
    assert len(result.items) == 1
    assert result.items[0].product_name_snapshot == "Basmati Rice 5kg"

    # Verify inventory was decremented and movement added
    assert balance.on_hand_quantity == 48
    assert balance.version == 2

    # Verify add calls on session (movement, order, order_item)
    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    movements = [obj for obj in added_objects if isinstance(obj, InventoryMovement)]
    assert len(movements) == 1
    assert movements[0].movement_type == MovementType.SALE.value
    assert movements[0].quantity_delta == -2
    assert movements[0].source_type == MovementSourceType.ORDER.value

    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_order_creation_insufficient_stock(
    mock_session: AsyncMock,
    mock_order_repo: AsyncMock,
    mock_inv_repo: AsyncMock,
    mock_prod_repo: AsyncMock,
    mock_cust_repo: AsyncMock,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    active_product: Product,
) -> None:
    service = OrderService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
        repository=mock_order_repo,
        inventory_repository=mock_inv_repo,
        product_repository=mock_prod_repo,
        customer_repository=mock_cust_repo,
    )

    mock_prod_repo.get_by_id.return_value = active_product
    balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=active_product.id,
        on_hand_quantity=1,
        version=1,
    )
    mock_inv_repo.get_balance_for_update.return_value = balance

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=active_product.id,
                quantity=5,
                unit_price_minor=120000,
            )
        ],
    )

    with pytest.raises(ValidationException) as exc_info:
        await service.create_order(req)

    assert "Insufficient stock" in str(exc_info.value)
    assert balance.on_hand_quantity == 1  # Unchanged



@pytest.mark.asyncio
async def test_order_creation_rejects_archived_product(
    mock_session: AsyncMock,
    mock_order_repo: AsyncMock,
    mock_inv_repo: AsyncMock,
    mock_prod_repo: AsyncMock,
    mock_cust_repo: AsyncMock,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    service = OrderService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
        repository=mock_order_repo,
        inventory_repository=mock_inv_repo,
        product_repository=mock_prod_repo,
        customer_repository=mock_cust_repo,
    )

    archived_prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code="SKU-ARCH",
        name="Old Item",
        base_unit="piece",
        default_price_minor=1000,
        currency_code="PKR",
        status=ProductStatus.ARCHIVED.value,
    )
    mock_prod_repo.get_by_id.return_value = archived_prod

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=archived_prod.id,
                quantity=1,
                unit_price_minor=1000,
            )
        ],
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_order(req)

    assert "Cannot order archived product" in str(exc_info.value)



@pytest.mark.asyncio
async def test_order_creation_rejects_archived_customer(
    mock_session: AsyncMock,
    mock_order_repo: AsyncMock,
    mock_inv_repo: AsyncMock,
    mock_prod_repo: AsyncMock,
    mock_cust_repo: AsyncMock,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    active_product: Product,
) -> None:
    service = OrderService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
        repository=mock_order_repo,
        inventory_repository=mock_inv_repo,
        product_repository=mock_prod_repo,
        customer_repository=mock_cust_repo,
    )

    archived_cust = Customer(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Archived Customer",
        phone="03009999999",
        status=CustomerStatus.ARCHIVED.value,
    )
    mock_cust_repo.get_by_id.return_value = archived_cust

    req = OrderCreateSchema(
        customer_id=archived_cust.id,
        items=[
            OrderItemCreateSchema(
                product_id=active_product.id,
                quantity=1,
                unit_price_minor=1000,
            )
        ],
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_order(req)

    assert "Cannot create order for archived customer" in str(exc_info.value)


@pytest.mark.asyncio
async def test_order_creation_permission_denied_for_unauthorized_role(
    mock_session: AsyncMock,
    mock_order_repo: AsyncMock,
    mock_inv_repo: AsyncMock,
    mock_prod_repo: AsyncMock,
    mock_cust_repo: AsyncMock,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    active_product: Product,
) -> None:
    # A dummy role or role without orders:create
    service = OrderService(
        session=mock_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role="anonymous_role",
        repository=mock_order_repo,
        inventory_repository=mock_inv_repo,
        product_repository=mock_prod_repo,
        customer_repository=mock_cust_repo,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=active_product.id,
                quantity=1,
                unit_price_minor=1000,
            )
        ],
    )

    with pytest.raises(AuthorizationException):
        await service.create_order(req)

"""Unit tests for Order and OrderItem schemas and models (ORD-001)."""

import uuid
import pytest
from pydantic import ValidationError

from app.modules.orders.enums import OrderStatus
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import (
    OrderCreateSchema,
    OrderItemCreateSchema,
)


def test_order_item_create_schema_validations() -> None:
    prod_id = uuid.uuid4()

    # Valid item
    item = OrderItemCreateSchema(
        product_id=prod_id,
        quantity=5,
        unit_price_minor=150000,
    )
    assert item.quantity == 5
    assert item.unit_price_minor == 150000

    # Non-positive quantity rejected
    with pytest.raises(ValidationError):
        OrderItemCreateSchema(product_id=prod_id, quantity=0, unit_price_minor=100)
    with pytest.raises(ValidationError):
        OrderItemCreateSchema(product_id=prod_id, quantity=-1, unit_price_minor=100)

    # Negative unit price rejected
    with pytest.raises(ValidationError):
        OrderItemCreateSchema(product_id=prod_id, quantity=2, unit_price_minor=-50)


def test_order_create_schema_validations() -> None:
    prod_id = uuid.uuid4()

    # Valid order
    order = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(product_id=prod_id, quantity=2, unit_price_minor=50000)
        ]
    )
    assert order.currency_code == "PKR"
    assert len(order.items) == 1
    assert order.customer_id is None

    # Empty items list rejected
    with pytest.raises(ValidationError):
        OrderCreateSchema(items=[])


def test_order_and_item_model_instantiation() -> None:
    org_id = uuid.uuid4()
    order_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    order = Order(
        id=order_id,
        organization_id=org_id,
        order_number="ORD-0001",
        customer_id=None,
        status=OrderStatus.ACTIVE.value,
        order_total_minor=100000,
        currency_code="PKR",
    )
    item = OrderItem(
        id=uuid.uuid4(),
        organization_id=org_id,
        order_id=order_id,
        product_id=prod_id,
        product_name_snapshot="Linen Shirt",
        product_code_snapshot="SHIRT-01",
        unit_snapshot="piece",
        quantity=2,
        unit_price_minor=50000,
        line_total_minor=100000,
        currency_code="PKR",
    )
    order.items.append(item)

    assert order.order_number == "ORD-0001"
    assert len(order.items) == 1
    assert order.items[0].product_name_snapshot == "Linen Shirt"
    assert order.items[0].line_total_minor == 100000

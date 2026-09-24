"""Unit tests for deterministic order calculation engine (ORD-002)."""

import uuid
import pytest

from app.core.errors import ValidationException
from app.modules.orders.calculator import OrderCalculator
from app.modules.orders.schemas import OrderItemCreateSchema


def test_calculate_line_total_deterministic_integer_arithmetic() -> None:
    # 2 shirts at PKR 1,500.00 (150,000 minor units) = PKR 3,000.00 (300,000 minor units)
    assert OrderCalculator.calculate_line_total(2, 150000) == 300000

    # 10 items at PKR 0.50 (50 minor units) = 500 minor units
    assert OrderCalculator.calculate_line_total(10, 50) == 500

    # Zero unit price (free item / bonus) = 0 minor units
    assert OrderCalculator.calculate_line_total(3, 0) == 0

    # Large realistic retail amount: 10,000 pieces at PKR 25,000.00 (2,500,000 minor units)
    assert OrderCalculator.calculate_line_total(10000, 2500000) == 25000000000


def test_calculate_line_total_rejects_invalid_values() -> None:
    # Zero quantity rejected
    with pytest.raises(ValidationException, match="positive integer"):
        OrderCalculator.calculate_line_total(0, 500)

    # Negative quantity rejected
    with pytest.raises(ValidationException, match="positive integer"):
        OrderCalculator.calculate_line_total(-5, 500)

    # Negative price rejected
    with pytest.raises(ValidationException, match="non-negative integer"):
        OrderCalculator.calculate_line_total(2, -100)

    # Floating point inputs rejected (zero float drift guarantee)
    with pytest.raises(ValidationException):
        OrderCalculator.calculate_line_total(2.5, 100)  # type: ignore[arg-type]
    with pytest.raises(ValidationException):
        OrderCalculator.calculate_line_total(2, 100.5)  # type: ignore[arg-type]


def test_calculate_order_totals_and_items() -> None:
    pid1 = uuid.uuid4()
    pid2 = uuid.uuid4()
    pid3 = uuid.uuid4()

    items = [
        OrderItemCreateSchema(product_id=pid1, quantity=2, unit_price_minor=150000),  # 300,000
        OrderItemCreateSchema(product_id=pid2, quantity=1, unit_price_minor=45000),   # 45,000
        OrderItemCreateSchema(product_id=pid3, quantity=5, unit_price_minor=2000),    # 10,000
    ]

    result = OrderCalculator.calculate_order(items, currency_code="PKR")

    assert result.currency_code == "PKR"
    assert result.subtotal_minor == 355000
    assert result.order_total_minor == 355000
    assert len(result.items) == 3

    assert result.items[0].product_id == pid1
    assert result.items[0].line_total_minor == 300000

    assert result.items[1].product_id == pid2
    assert result.items[1].line_total_minor == 45000

    assert result.items[2].product_id == pid3
    assert result.items[2].line_total_minor == 10000


def test_calculate_order_validates_currency_and_empty_list() -> None:
    pid = uuid.uuid4()

    # Empty items rejected
    with pytest.raises(ValidationException, match="at least one line item"):
        OrderCalculator.calculate_order([])

    # Invalid currency code rejected
    with pytest.raises(ValidationException, match="Invalid currency code"):
        OrderCalculator.calculate_order(
            [OrderItemCreateSchema(product_id=pid, quantity=1, unit_price_minor=100)],
            currency_code="PK",
        )

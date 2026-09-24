"""Pure deterministic order financial calculation engine (ORD-002).

Enforces strictly integer minor-currency arithmetic (e.g. paisas for PKR).
Completely avoids binary floating-point representation bugs, rounding errors,
or non-deterministic calculation drift.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from app.core.errors import ValidationException
from app.modules.orders.schemas import OrderItemCreateSchema

MAX_SAFE_MINOR_AMOUNT = 9_000_000_000_000_000  # Safe within 64-bit integer limits


@dataclass(frozen=True)
class CalculatedLineItem:
    """Deterministically calculated line item."""

    product_id: uuid.UUID
    quantity: int
    unit_price_minor: int
    line_total_minor: int


@dataclass(frozen=True)
class OrderCalculationResult:
    """Deterministic order calculation totals."""

    items: tuple[CalculatedLineItem, ...]
    subtotal_minor: int
    order_total_minor: int
    currency_code: str


class OrderCalculator:
    """Stateless calculation service for orders and line items."""

    @staticmethod
    def calculate_line_total(quantity: int, unit_price_minor: int) -> int:
        """Calculate line item total deterministically.

        Must satisfy:
        - quantity is positive integer (> 0).
        - unit_price_minor is non-negative integer (>= 0).
        - line_total_minor = quantity * unit_price_minor.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValidationException(f"Quantity must be a positive integer, got {quantity}")

        if not isinstance(unit_price_minor, int) or unit_price_minor < 0:
            raise ValidationException(
                f"Unit price in minor units must be a non-negative integer, got {unit_price_minor}"
            )

        line_total = quantity * unit_price_minor
        if line_total > MAX_SAFE_MINOR_AMOUNT:
            raise ValidationException("Line item total exceeds maximum supported financial limit")

        return line_total

    @classmethod
    def calculate_order(
        cls,
        items: Sequence[OrderItemCreateSchema | dict],
        currency_code: str = "PKR",
    ) -> OrderCalculationResult:
        """Calculate order totals and item totals using integer arithmetic only."""
        if not items:
            raise ValidationException("Order must contain at least one line item")

        currency = currency_code.strip().upper()
        if len(currency) != 3:
            raise ValidationException(f"Invalid currency code '{currency_code}'. Must be 3 characters.")

        calculated_items: list[CalculatedLineItem] = []
        running_total = 0

        for item in items:
            if isinstance(item, OrderItemCreateSchema):
                pid = item.product_id
                qty = item.quantity
                price = item.unit_price_minor
            else:
                pid = item["product_id"]
                qty = item["quantity"]
                price = item["unit_price_minor"]

            line_total = cls.calculate_line_total(qty, price)
            running_total += line_total

            if running_total > MAX_SAFE_MINOR_AMOUNT:
                raise ValidationException("Order total exceeds maximum supported financial limit")

            calculated_items.append(
                CalculatedLineItem(
                    product_id=pid,
                    quantity=qty,
                    unit_price_minor=price,
                    line_total_minor=line_total,
                )
            )

        return OrderCalculationResult(
            items=tuple(calculated_items),
            subtotal_minor=running_total,
            order_total_minor=running_total,
            currency_code=currency,
        )

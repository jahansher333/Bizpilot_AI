"""Enums for Order lifecycle (ORD-001)."""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    """Order lifecycle status."""

    ACTIVE = "active"
    VOIDED = "voided"
    CORRECTED = "corrected"

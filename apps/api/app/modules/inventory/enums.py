"""Inventory enums for movement and source types (INV-001)."""

from __future__ import annotations

from enum import Enum


class MovementType(str, Enum):
    """Allowed inventory movement types."""

    OPENING = "opening"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    CORRECTION = "correction"
    VOID_REVERSAL = "void_reversal"


class MovementSourceType(str, Enum):
    """Source classification for inventory movements."""

    OPENING = "opening"
    ORDER = "order"
    ADJUSTMENT = "adjustment"
    CORRECTION = "correction"
    VOID_REVERSAL = "void_reversal"

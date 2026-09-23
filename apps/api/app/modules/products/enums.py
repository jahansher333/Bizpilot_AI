"""Product domain enumerations (CAT-002)."""

from __future__ import annotations

from enum import StrEnum


class ProductStatus(StrEnum):
    """Lifecycle status for products."""

    ACTIVE = "active"
    ARCHIVED = "archived"

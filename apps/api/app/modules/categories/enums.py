"""Enumerations for category domain entities (CAT-001)."""

from __future__ import annotations

from enum import StrEnum


class CategoryStatus(StrEnum):
    """Lifecycle states for categories."""

    ACTIVE = "active"
    ARCHIVED = "archived"

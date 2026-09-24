"""Enums for Customer lifecycle (CUS-001)."""

from __future__ import annotations

from enum import StrEnum


class CustomerStatus(StrEnum):
    """Customer lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"

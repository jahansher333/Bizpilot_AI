"""Enums for Payment lifecycle and channels (PAY-001)."""

from __future__ import annotations

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Payment lifecycle status."""

    ACTIVE = "active"
    VOIDED = "voided"
    CORRECTED = "corrected"


class PaymentChannel(StrEnum):
    """Payment receipt channel."""

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    DIGITAL = "digital"
    OTHER = "other"

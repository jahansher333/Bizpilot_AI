"""Domain enums for tenant-scoped expenses and categories (EXP-001)."""

from enum import Enum


class ExpenseCategoryStatus(str, Enum):
    """Lifecycle status for expense categories."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ExpenseStatus(str, Enum):
    """Lifecycle status for operational expenses."""

    ACTIVE = "active"
    VOIDED = "voided"
    CORRECTED = "corrected"


class ExpensePaymentMethod(str, Enum):
    """Payment method used for recorded operational expense."""

    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    MOBILE_WALLET = "mobile_wallet"
    DIGITAL = "digital"
    OTHER = "other"

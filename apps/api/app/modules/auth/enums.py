"""Authentication domain enums."""

from enum import StrEnum


class UserStatus(StrEnum):
    """Account lifecycle status for users."""

    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"

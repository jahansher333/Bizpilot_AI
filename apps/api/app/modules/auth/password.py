"""Argon2id password service and bounded password policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher, Type
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.config import Settings, get_settings
from app.core.errors import ValidationException

# Bounded project-owned denylist of obvious, common, or predictable passwords.
# Normalization (trimming and lowercasing) is performed for policy matching ONLY.
COMMON_PASSWORDS_DENYLIST: frozenset[str] = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "123456789012345",
        "password1234",
        "password12345",
        "password123456",
        "adminadminadmin",
        "administrator1",
        "letmeinletmein",
        "welcome123456",
        "qwertyuiopas",
        "qwertyuiopasd",
        "qwertyuiopasdf",
        "iloveyouiloveyou",
        "monkeymonkeymonkey",
        "dragon123456",
        "sunshine12345",
        "princess12345",
        "football12345",
        "charlie123456",
        "superman12345",
        "trustno1trustno1",
        "changeit12345",
        "secret123456",
        "default12345",
        "passcode12345",
        "bizpilot1234",
        "bizpilot12345",
        "bizpilot2026",
        "pakistan1234",
        "pakistan12345",
        "karachi12345",
        "lahore123456",
        "islamabad123",
        "access123456",
        "master123456",
        "shadow123456",
        "system123456",
        "testing12345",
    }
)


@dataclass(frozen=True)
class PasswordVerificationResult:
    """Result of a password verification check."""

    valid: bool
    needs_rehash: bool = False


class PasswordService:
    """Domain service for Argon2id password hashing, verification, and policy enforcement."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        cfg = settings or get_settings()
        self._min_length = cfg.auth.password_min_length
        self._max_length = cfg.auth.password_max_length

        self._hasher = PasswordHasher(
            time_cost=cfg.auth.argon2_time_cost,
            memory_cost=cfg.auth.argon2_memory_cost_kib,
            parallelism=cfg.auth.argon2_parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

        # Pre-computed dummy hash using the exact active parameters for constant-work dummy verification
        self._dummy_hash = self._hasher.hash("dummy-password-for-timing-mitigation")

    def validate_password_policy(self, plain_password: str) -> None:
        """Validate password against length constraints and the bounded common denylist.

        Important: Normalization is used for policy comparison ONLY. The password
        is never altered or transformed for hashing.
        """
        if len(plain_password) < self._min_length:
            raise ValidationException(
                message=f"Password must be at least {self._min_length} characters long"
            )

        if len(plain_password) > self._max_length:
            raise ValidationException(
                message=f"Password exceeds maximum allowed length of {self._max_length} characters"
            )

        # Policy normalization: check against common denylist
        normalized_for_policy = plain_password.strip().lower()
        if normalized_for_policy in COMMON_PASSWORDS_DENYLIST:
            raise ValidationException(
                message="The chosen password is too common or easily guessed"
            )

    def hash_password(self, plain_password: str) -> str:
        """Validate policy and hash the exact supplied password using Argon2id."""
        self.validate_password_policy(plain_password)
        # Hash the exact untransformed password
        return self._hasher.hash(plain_password)

    def verify_password(
        self, plain_password: str, password_hash: str
    ) -> PasswordVerificationResult:
        """Verify plain password against stored Argon2id hash using library primitive.

        Fails closed on corrupt, invalid, or mismatched hashes.
        """
        if not password_hash or not isinstance(password_hash, str) or not password_hash.strip():
            return PasswordVerificationResult(valid=False, needs_rehash=False)

        try:
            # Uses argon2-cffi native constant-time verification primitive
            self._hasher.verify(password_hash, plain_password)
            needs_rehash = self._hasher.check_needs_rehash(password_hash)
            return PasswordVerificationResult(valid=True, needs_rehash=needs_rehash)
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return PasswordVerificationResult(valid=False, needs_rehash=False)
        except Exception:
            # Fail closed on any unexpected verification issue
            return PasswordVerificationResult(valid=False, needs_rehash=False)

    def verify_dummy(self) -> None:
        """Perform comparable Argon2id verification work against a dummy hash.

        Used by login orchestration (AUTH-004) when a user lookup fails to prevent
        account enumeration via timing differences.
        """
        try:
            self._hasher.verify(self._dummy_hash, "dummy-password-for-timing-mitigation")
        except Exception:
            pass

    def needs_rehash(self, password_hash: str) -> bool:
        """Check if stored hash was created with parameters differing from current target."""
        if not password_hash or not isinstance(password_hash, str):
            return False
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except Exception:
            return False

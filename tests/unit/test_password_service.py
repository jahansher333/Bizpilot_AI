"""Unit tests for PasswordService, Argon2id hashing, and password policy."""

import pytest

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.core.errors import ValidationException
from app.modules.auth.password import PasswordService


@pytest.fixture
def fast_test_settings() -> Settings:
    """Provide isolated lightweight Argon2id parameters for fast unit tests."""
    return Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="test-only-signing-secret",
            password_min_length=12,
            password_max_length=128,
            argon2_time_cost=1,
            argon2_memory_cost_kib=8192,
            argon2_parallelism=1,
        ),
    )


def test_production_config_distinct_from_test_overrides() -> None:
    """Verify that default production Settings() has the approved P0 baseline parameters.

    Confirms that test overrides do not alter production defaults.
    """
    settings = Settings(
        environment=EnvironmentMode.LOCAL,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_dev"
        ),
        auth=AuthenticationSettings(signing_secret="local-dev-signing-secret"),
    )
    # Approved production defaults
    assert settings.auth.argon2_memory_cost_kib == 65536
    assert settings.auth.argon2_time_cost == 3
    assert settings.auth.argon2_parallelism == 4
    assert settings.auth.password_min_length == 12
    assert settings.auth.password_max_length == 128


def test_hash_password_produces_argon2id_format(fast_test_settings: Settings) -> None:
    """Verify generated hash is a valid Argon2id formatted string."""
    service = PasswordService(fast_test_settings)
    raw_password = "correct horse battery staple"
    hashed = service.hash_password(raw_password)

    assert isinstance(hashed, str)
    assert hashed.startswith("$argon2id$v=19$")
    assert "m=8192,t=1,p=1" in hashed
    assert raw_password not in hashed


def test_verify_password_success(fast_test_settings: Settings) -> None:
    """Verify correct plaintext password validates against hash."""
    service = PasswordService(fast_test_settings)
    raw_password = "my secure long passphrase"
    hashed = service.hash_password(raw_password)

    result = service.verify_password(raw_password, hashed)
    assert result.valid is True
    assert result.needs_rehash is False


def test_verify_password_wrong_password(fast_test_settings: Settings) -> None:
    """Verify incorrect plaintext password fails verification."""
    service = PasswordService(fast_test_settings)
    raw_password = "my secure long passphrase"
    hashed = service.hash_password(raw_password)

    result = service.verify_password("wrong password attempt", hashed)
    assert result.valid is False
    assert result.needs_rehash is False


def test_policy_accepts_valid_passphrase(fast_test_settings: Settings) -> None:
    """Verify legitimate passphrase without symbols or numbers passes policy.

    Confirms modern policy does NOT enforce predictable complexity rules.
    """
    service = PasswordService(fast_test_settings)
    # Simple multi-word phrase with only lowercase letters and spaces
    passphrase = "correct horse battery staple"
    service.validate_password_policy(passphrase)  # Must not raise


def test_policy_rejects_too_short(fast_test_settings: Settings) -> None:
    """Verify passwords shorter than minimum length raise ValidationException."""
    service = PasswordService(fast_test_settings)
    with pytest.raises(ValidationException, match="at least 12 characters"):
        service.validate_password_policy("shortpass12")


def test_policy_rejects_too_long(fast_test_settings: Settings) -> None:
    """Verify passwords exceeding maximum length raise ValidationException."""
    service = PasswordService(fast_test_settings)
    excessive_password = "a" * 129
    with pytest.raises(ValidationException, match="exceeds maximum allowed length"):
        service.validate_password_policy(excessive_password)


def test_policy_rejects_denylisted_password(fast_test_settings: Settings) -> None:
    """Verify bounded denylist matches raise ValidationException."""
    service = PasswordService(fast_test_settings)
    with pytest.raises(ValidationException, match="too common or easily guessed"):
        service.validate_password_policy("password123456")

    with pytest.raises(ValidationException, match="too common or easily guessed"):
        service.validate_password_policy("adminadminadmin")


def test_policy_denylist_normalization(fast_test_settings: Settings) -> None:
    """Verify denylist matching normalizes case and surrounding whitespace for policy comparison."""
    service = PasswordService(fast_test_settings)
    # Uppercase with spaces matching denylisted 'password123456'
    with pytest.raises(ValidationException, match="too common or easily guessed"):
        service.validate_password_policy("  PASSWORD123456  ")


def test_exact_password_not_normalized_for_hashing(fast_test_settings: Settings) -> None:
    """Verify the exact supplied password is preserved for hashing (spaces/case not altered)."""
    service = PasswordService(fast_test_settings)
    exact_password = "  valid secret passphrase 123  "
    hashed = service.hash_password(exact_password)

    # Verification with exact password must succeed
    assert service.verify_password(exact_password, hashed).valid is True

    # Verification with trimmed password must fail because hashing did not trim it
    assert service.verify_password(exact_password.strip(), hashed).valid is False


def test_needs_rehash_detection() -> None:
    """Verify that a hash generated with lower cost parameters triggers needs_rehash=True."""
    # Hasher configured with lower cost
    old_settings = Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="test-only-signing-secret",
            argon2_time_cost=1,
            argon2_memory_cost_kib=8192,
            argon2_parallelism=1,
        ),
    )
    old_service = PasswordService(old_settings)
    old_hash = old_service.hash_password("valid password for test")

    # Target service with higher cost
    new_settings = Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="test-only-signing-secret",
            argon2_time_cost=2,
            argon2_memory_cost_kib=16384,
            argon2_parallelism=2,
        ),
    )
    new_service = PasswordService(new_settings)

    # Verification succeeds but signals needs_rehash=True
    result = new_service.verify_password("valid password for test", old_hash)
    assert result.valid is True
    assert result.needs_rehash is True

    # Standalone needs_rehash check also returns True
    assert new_service.needs_rehash(old_hash) is True

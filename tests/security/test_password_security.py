"""Security-focused tests for password hashing, timing mitigation, and safe failure modes."""

import inspect
import logging

import pytest

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.modules.auth.password import PasswordService


@pytest.fixture
def test_password_service() -> PasswordService:
    settings = Settings(
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
    return PasswordService(settings)


def test_malformed_hash_fails_closed(test_password_service: PasswordService) -> None:
    """Verify that corrupt, truncated, or invalid hashes fail closed safely without crashing."""
    service = test_password_service
    plain = "correct horse battery staple"

    # Malformed / truncated hashes
    assert service.verify_password(plain, "").valid is False
    assert service.verify_password(plain, "   ").valid is False
    assert service.verify_password(plain, "not_a_valid_argon2_hash").valid is False
    assert service.verify_password(plain, "$argon2id$v=19$m=65536,t=3,p=4$corrupt").valid is False
    assert service.verify_password(plain, "$argon2id$v=19$").valid is False
    assert service.verify_password(plain, "$argon2id$invalid_params$dummy$dummy").valid is False
    assert service.verify_password(plain, "$argon2d$v=19$m=8192,t=1,p=1$abc$def").valid is False


def test_dummy_verification_primitive(test_password_service: PasswordService) -> None:
    """Verify verify_dummy executes full Argon2 verification work without throwing exceptions."""
    service = test_password_service
    # Must complete cleanly without error
    service.verify_dummy()


def test_unicode_password_hashing_and_verification(
    test_password_service: PasswordService,
) -> None:
    """Verify passwords containing multi-byte UTF-8 Unicode characters (Urdu/Arabic/emojis) hash and verify correctly."""
    service = test_password_service
    unicode_password = "میرا محفوظ پاس ورڈ ۲۰۲۶ 🔐"

    hashed = service.hash_password(unicode_password)
    assert isinstance(hashed, str)

    result = service.verify_password(unicode_password, hashed)
    assert result.valid is True

    # Tampered unicode character must fail
    wrong_unicode = "میرا محفوظ پاس ورڈ ۲۰۲۵ 🔐"
    assert service.verify_password(wrong_unicode, hashed).valid is False


def test_no_plaintext_password_in_logging(
    test_password_service: PasswordService, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify plaintext passwords and secret hashes are never captured in application logs."""
    service = test_password_service
    secret_plain = "super_secret_unmasked_plain_password_123"

    with caplog.at_level(logging.DEBUG):
        hashed = service.hash_password(secret_plain)
        service.verify_password(secret_plain, hashed)
        service.verify_password("wrong_password_attempt_456", hashed)

    for record in caplog.records:
        assert secret_plain not in record.message
        assert hashed not in record.message
        assert "wrong_password_attempt_456" not in record.message


def test_cryptographic_verification_primitive_used() -> None:
    """Verify that PasswordService relies on the compiled library primitive and has no custom string comparison."""
    source = inspect.getsource(PasswordService.verify_password)
    # Must call the library verify method
    assert "self._hasher.verify" in source
    # Must NOT implement custom string equality on hashes
    assert "password_hash ==" not in source
    assert "==" not in source or "isinstance" in source


def test_no_permanent_lockout_mechanism() -> None:
    """Verify that PasswordService and AccountPolicyService implement no permanent lockout counter."""
    from app.modules.auth.account_policy import AccountPolicyService

    pwd_source = inspect.getsource(PasswordService)
    acc_source = inspect.getsource(AccountPolicyService)

    assert "lockout" not in pwd_source.lower()
    assert "failed_attempts" not in pwd_source.lower()
    assert "failed_attempts" not in acc_source.lower()

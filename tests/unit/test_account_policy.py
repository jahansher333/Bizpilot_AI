"""Unit tests for AccountPolicyService."""

import pytest

from app.core.errors import AuthenticationException
from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User


def test_account_policy_allows_active() -> None:
    """Verify active user status permits authentication."""
    service = AccountPolicyService()
    user = User(
        email_normalized="active@example.com",
        display_name="Active User",
        status=UserStatus.ACTIVE.value,
    )
    # Must not raise
    service.verify_user_can_authenticate(user)


def test_account_policy_rejects_disabled() -> None:
    """Verify disabled user status raises AuthenticationException."""
    service = AccountPolicyService()
    user = User(
        email_normalized="disabled@example.com",
        display_name="Disabled User",
        status=UserStatus.DISABLED.value,
    )
    with pytest.raises(AuthenticationException, match="Account is disabled"):
        service.verify_user_can_authenticate(user)


def test_account_policy_rejects_pending() -> None:
    """Verify pending user status raises AuthenticationException."""
    service = AccountPolicyService()
    user = User(
        email_normalized="pending@example.com",
        display_name="Pending User",
        status=UserStatus.PENDING.value,
    )
    with pytest.raises(AuthenticationException, match="Account activation pending"):
        service.verify_user_can_authenticate(user)


def test_account_policy_rejects_unknown_status() -> None:
    """Verify unknown status raises AuthenticationException."""
    service = AccountPolicyService()
    user = User(
        email_normalized="unknown@example.com",
        display_name="Unknown Status User",
        status="suspended",
    )
    with pytest.raises(AuthenticationException, match="Invalid account status"):
        service.verify_user_can_authenticate(user)

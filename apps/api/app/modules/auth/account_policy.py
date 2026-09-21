"""Account lifecycle policy enforcement service."""

from __future__ import annotations

from app.core.errors import AuthenticationException
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import User


class AccountPolicyService:
    """Domain service for enforcing user account lifecycle authentication eligibility."""

    def verify_user_can_authenticate(self, user: User) -> None:
        """Verify whether the user account state permits authentication.

        ACTIVE: allowed
        DISABLED: rejected with AuthenticationError
        PENDING: rejected with AuthenticationError
        """
        if user.status == UserStatus.ACTIVE.value:
            return

        if user.status == UserStatus.DISABLED.value:
            raise AuthenticationException(message="Account is disabled")

        if user.status == UserStatus.PENDING.value:
            raise AuthenticationException(message="Account activation pending")

        raise AuthenticationException(message="Invalid account status")

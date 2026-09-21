"""Auth module exports."""

from app.modules.auth.account_policy import AccountPolicyService
from app.modules.auth.enums import UserStatus
from app.modules.auth.models import (
    PasswordResetToken,
    RefreshToken,
    User,
    UserCredential,
    generate_uuid,
)
from app.modules.auth.password import (
    COMMON_PASSWORDS_DENYLIST,
    PasswordService,
    PasswordVerificationResult,
)
from app.modules.auth.logout import LogoutService
from app.modules.auth.refresh import (
    RefreshService,
    generate_refresh_token,
    hash_refresh_token,
)
from app.modules.auth.repository import AuthRepository
from app.modules.auth.router import router as auth_router
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    UserMeResponse,
)
from app.modules.auth.service import LoginService, RegistrationService
from app.modules.auth.tokens import (
    AccessTokenResult,
    AuthenticatedUser,
    TokenService,
    get_current_user,
)

__all__ = [
    "AccessTokenResult",
    "AccountPolicyService",
    "AuthRepository",
    "AuthenticatedUser",
    "COMMON_PASSWORDS_DENYLIST",
    "LoginRequest",
    "LoginResponse",
    "LoginService",
    "LogoutRequest",
    "LogoutResponse",
    "LogoutService",
    "PasswordResetToken",
    "PasswordService",
    "PasswordVerificationResult",
    "RefreshToken",
    "RefreshRequest",
    "RefreshResponse",
    "RefreshService",
    "RegisterRequest",
    "RegisterResponse",
    "RegistrationService",
    "TokenService",
    "User",
    "UserCredential",
    "UserMeResponse",
    "UserStatus",
    "auth_router",
    "generate_refresh_token",
    "generate_uuid",
    "get_current_user",
    "hash_refresh_token",
]

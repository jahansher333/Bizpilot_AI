"""FastAPI router for authentication and registration endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeVar

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationException, RateLimitException
from app.db.session import get_session
from app.modules.auth.cookies import (
    clear_refresh_cookie,
    read_refresh_cookie,
    require_trusted_origin,
    set_refresh_cookie,
)
from app.modules.auth.logout import LogoutService
from app.modules.auth.rate_limit import RATE_LIMIT_MESSAGE, AuthRateLimiter
from app.modules.auth.recovery import PasswordRecoveryService
from app.modules.auth.refresh import RefreshService
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SessionResponse,
    UserMeResponse,
)
from app.modules.auth.service import LoginService, RegistrationService
from app.modules.auth.tokens import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_CookieRequestT = TypeVar("_CookieRequestT", RefreshRequest, LogoutRequest)


def _client_ip(http_request: Request) -> str:
    # Socket peer address only; X-Forwarded-For is trusted solely via the server's proxy-headers config.
    return http_request.client.host if http_request.client else "unknown"


def _rate_limiter(session: AsyncSession, http_request: Request) -> AuthRateLimiter:
    return AuthRateLimiter(session, getattr(http_request.app.state, "settings", None))


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new user account",
    description="Registers a user account. Returns a uniform 202 Accepted response without revealing account existence.",
)
async def register(
    request: RegisterRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    """Handle user registration with per-IP request limiting."""
    allowed = await _rate_limiter(session, http_request).consume_register(_client_ip(http_request))
    # Commit the counter first so it survives any later rollback of the request transaction.
    await session.commit()
    if not allowed:
        raise RateLimitException(RATE_LIMIT_MESSAGE)
    service = RegistrationService(session)
    return await service.register(request)


@router.post(
    "/login",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain an access token",
    description=(
        "Authenticates credentials and returns a short-lived Bearer access token. The refresh token "
        "is set as the HttpOnly bizpilot_refresh cookie and never appears in the body."
    ),
)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """Handle user login with per (email, IP) failed-attempt limiting."""
    limiter = _rate_limiter(session, http_request)
    client_ip = _client_ip(http_request)
    await limiter.ensure_login_allowed(request.email, client_ip)

    service = LoginService(session)
    try:
        result = await service.login(request)
    except AuthenticationException:
        # Persist the failure before the request transaction rolls back.
        await limiter.record_login_failure(request.email, client_ip)
        await session.commit()
        raise

    await limiter.clear_login_failures(request.email, client_ip)
    return _issue_session(response, result)


def _issue_session(response: Response, result: LoginResponse | RefreshResponse) -> SessionResponse:
    """Move the refresh token into its cookie and return only the access token."""
    expires_at = result.refresh_expires_at or datetime.now(timezone.utc)
    set_refresh_cookie(response, result.refresh_token, expires_at)
    return SessionResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


def _cookie_request(http_request: Request, model: type[_CookieRequestT]) -> _CookieRequestT:
    """Build the service request from the refresh cookie; a missing or malformed cookie is a 401."""
    raw_token = read_refresh_cookie(http_request)
    try:
        return model(refresh_token=raw_token)
    except ValidationError:
        raise AuthenticationException("Invalid or expired refresh token") from None


@router.post(
    "/refresh",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and obtain a new access token",
    description=(
        "Rotates the single-use refresh token from the bizpilot_refresh cookie, sets its successor "
        "as the new cookie, and returns a new access token."
    ),
    dependencies=[Depends(require_trusted_origin)],
)
async def refresh(
    http_request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """Handle refresh token rotation with per-IP request limiting."""
    allowed = await _rate_limiter(session, http_request).consume_refresh(_client_ip(http_request))
    # Commit the counter first so rejected (rolled back) refresh attempts still count.
    await session.commit()
    if not allowed:
        raise RateLimitException(RATE_LIMIT_MESSAGE)
    service = RefreshService(session)
    result = await service.refresh(_cookie_request(http_request, RefreshRequest))
    return _issue_session(response, result)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout current session",
    description="Revokes the refresh token family of the bizpilot_refresh cookie and clears the cookie.",
    dependencies=[Depends(require_trusted_origin)],
)
async def logout(
    http_request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> LogoutResponse:
    """Handle current session logout."""
    service = LogoutService(session)
    result = await service.logout_current_session(_cookie_request(http_request, LogoutRequest))
    clear_refresh_cookie(response)
    return result


@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout all active sessions",
    description="Revokes all active refresh sessions belonging to the authenticated user.",
)
async def logout_all(
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LogoutResponse:
    """Handle logout-all-devices for authenticated principal."""
    service = LogoutService(session)
    result = await service.logout_all_sessions(current_user.id)
    clear_refresh_cookie(response)
    return result


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate password recovery",
    description="Initiates password recovery for the specified email. Returns a uniform non-enumerating 200 response.",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
) -> ForgotPasswordResponse:
    """Handle password recovery initiation with per-email request limiting."""
    allowed = await _rate_limiter(session, http_request).consume_forgot_password(request.email)
    # Commit the counter first so it survives any later rollback of the request transaction.
    await session.commit()
    if not allowed:
        raise RateLimitException(RATE_LIMIT_MESSAGE)
    service = PasswordRecoveryService(session)
    return await service.request_password_reset(request)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete password reset",
    description="Redeems a single-use password reset token and updates the user credential.",
)
async def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
) -> ResetPasswordResponse:
    """Handle password reset redemption with per-IP request limiting."""
    allowed = await _rate_limiter(session, http_request).consume_reset_password(_client_ip(http_request))
    # Commit the counter first so invalid-token attempts still count after a rollback.
    await session.commit()
    if not allowed:
        raise RateLimitException(RATE_LIMIT_MESSAGE)
    service = PasswordRecoveryService(session)
    return await service.reset_password(request)


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user identity",
    description="Returns the verified minimal identity of the currently authenticated principal.",
)
async def me(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserMeResponse:
    """Return authenticated principal identity."""
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email_normalized,
        display_name=current_user.display_name,
        status=current_user.status,
    )

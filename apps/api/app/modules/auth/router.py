"""FastAPI router for authentication and registration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserMeResponse,
)
from app.modules.auth.service import LoginService, RegistrationService
from app.modules.auth.tokens import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new user account",
    description="Registers a user account. Returns a uniform 202 Accepted response without revealing account existence.",
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    """Handle user registration."""
    service = RegistrationService(session)
    return await service.register(request)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain an access token",
    description="Authenticates credentials and returns a short-lived symmetric Bearer access token.",
)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """Handle user login."""
    service = LoginService(session)
    return await service.login(request)


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

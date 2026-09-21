"""FastAPI router for authentication and registration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.schemas import RegisterRequest, RegisterResponse
from app.modules.auth.service import RegistrationService

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

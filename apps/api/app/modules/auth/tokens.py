"""JWT token issuance, verification, and authenticated principal extraction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationException
from app.db.session import get_session
from app.modules.auth.enums import UserStatus
from app.modules.auth.repository import AuthRepository

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AccessTokenResult:
    """Result of access token issuance."""

    token: str
    expires_in: int


@dataclass(frozen=True)
class AuthenticatedUser:
    """Minimal typed identity for an authenticated principal."""

    id: uuid.UUID
    email_normalized: str
    display_name: str
    status: str


class TokenService:
    """Domain service for symmetric HS256 JWT access-token lifecycle with key rotation."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        cfg = settings or get_settings()
        self._secret = cfg.auth.signing_secret.get_secret_value()
        self._previous_secrets = [
            s.get_secret_value() for s in cfg.auth.previous_signing_secrets
        ]
        self._ttl_minutes = cfg.auth.access_token_minutes
        self._ttl_seconds = self._ttl_minutes * 60
        self._issuer = cfg.auth.jwt_issuer
        self._audience = cfg.auth.jwt_audience
        self._algorithm = "HS256"

    @property
    def ttl_seconds(self) -> int:
        """Configured access token lifetime in seconds."""
        return self._ttl_seconds

    def issue_access_token(self, user_id: uuid.UUID) -> AccessTokenResult:
        """Issue a short-lived symmetric HS256 JWT access token with unprivileged claims."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self._ttl_minutes)
        jti = str(uuid.uuid4())

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "jti": jti,
            "type": "access",
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return AccessTokenResult(token=token, expires_in=self._ttl_seconds)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT access token.

        Supports key rotation by attempting active signing secret, then previous secrets.
        Enforces HS256, expiration, nbf, issuer, audience, and type == 'access'.
        """
        if not token or not isinstance(token, str) or not token.strip():
            raise AuthenticationException("Invalid authentication token")

        # Candidate verification secrets: active first, then previous rotation keys
        secrets = [self._secret] + self._previous_secrets
        payload: Optional[dict[str, Any]] = None
        last_error: Optional[Exception] = None

        for secret in secrets:
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=[self._algorithm],
                    issuer=self._issuer,
                    audience=self._audience,
                    options={
                        "require": ["sub", "exp", "iat", "nbf", "jti", "type", "iss", "aud"],
                        "verify_exp": True,
                        "verify_iat": True,
                        "verify_nbf": True,
                        "verify_iss": True,
                        "verify_aud": True,
                    },
                )
                break
            except jwt.InvalidSignatureError as err:
                last_error = err
                continue
            except jwt.ExpiredSignatureError:
                raise AuthenticationException("Authentication token has expired")
            except (jwt.InvalidTokenError, Exception):
                raise AuthenticationException("Invalid authentication token")

        if payload is None:
            raise AuthenticationException("Invalid authentication token")

        if payload.get("type") != "access":
            raise AuthenticationException("Invalid authentication token type")

        # Validate that subject parses as UUID
        try:
            uuid.UUID(str(payload.get("sub")))
        except (ValueError, TypeError):
            raise AuthenticationException("Invalid authentication token subject")

        return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedUser:
    """FastAPI dependency for extracting and verifying trusted authenticated identity."""
    if not credentials or not credentials.credentials:
        raise AuthenticationException("Authentication required")

    token_service = TokenService()
    payload = token_service.decode_access_token(credentials.credentials)

    user_id = uuid.UUID(payload["sub"])
    repo = AuthRepository(session)
    user = await repo.get_user_by_id(user_id)

    if user is None:
        raise AuthenticationException("User account not found")

    if user.status != UserStatus.ACTIVE.value:
        raise AuthenticationException("User account is not active")

    return AuthenticatedUser(
        id=user.id,
        email_normalized=user.email_normalized,
        display_name=user.display_name,
        status=user.status,
    )

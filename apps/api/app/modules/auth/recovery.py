"""Domain service for password recovery, reset token lifecycle, and delivery (AUTH-007)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional, Protocol, runtime_checkable
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EmailSettings, Settings, get_settings
from app.core.errors import AuthenticationException, ValidationException
from app.modules.auth.enums import UserStatus
from app.modules.auth.password import PasswordService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.modules.auth.service import AccountPolicyService

logger = logging.getLogger(__name__)


def generate_password_reset_token() -> str:
    """Generate a high-entropy, URL-safe random reset token (256 bits entropy)."""
    return secrets.token_urlsafe(32)


def hash_password_reset_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hex digest for reset token lookup."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


@runtime_checkable
class PasswordResetDeliveryAdapter(Protocol):
    """Abstract port for delivering password reset tokens to users."""

    async def deliver_password_reset_token(
        self,
        email: str,
        reset_token: str,
    ) -> None:
        """Deliver the raw password reset token to the designated recipient."""
        ...


class InMemoryPasswordResetDeliveryAdapter:
    """In-memory recording adapter for testing and local verification."""

    def __init__(self) -> None:
        self.dispatches: list[dict[str, str]] = []

    async def deliver_password_reset_token(
        self,
        email: str,
        reset_token: str,
    ) -> None:
        self.dispatches.append({"email": email, "token": reset_token})

    def clear(self) -> None:
        self.dispatches.clear()


class DevelopmentLoggingPasswordResetDeliveryAdapter:
    """Default provider-independent local/development delivery adapter.

    Logs password-recovery dispatch events locally without delivering real emails,
    and strictly avoids leaking sensitive tokens, hashes, or passwords into logs.
    """

    async def deliver_password_reset_token(
        self,
        email: str,
        reset_token: str,
    ) -> None:
        # Sanitized audit: never log raw reset token, hash, or secrets
        logger.info(
            "Password recovery requested; local development dispatch recorded (no external email sent)",
            extra={"recipient_email": email},
        )


# Backward-compatible alias
LoggingPasswordResetDeliveryAdapter = DevelopmentLoggingPasswordResetDeliveryAdapter


class SmtpPasswordResetDeliveryAdapter:
    """Sends the reset link by SMTP (FIX-004).

    Sending is handed to a worker thread and not awaited, so the forgot-password response
    time does not reveal whether an account exists and SMTP failures never change the
    uniform response. Failures are logged without the token.
    """

    def __init__(self, settings: EmailSettings) -> None:
        if not settings.smtp_enabled or not settings.from_address:
            raise ValueError("SMTP delivery requires smtp_host and from_address")
        self._settings = settings
        self._pending: set[asyncio.Future[None]] = set()

    def build_message(self, email: str, reset_token: str) -> EmailMessage:
        base_url = self._settings.frontend_base_url.rstrip("/")
        reset_link = f"{base_url}/reset-password?{urlencode({'token': reset_token})}"
        message = EmailMessage()
        message["Subject"] = "Reset your BizPilot AI password"
        message["From"] = self._settings.from_address
        message["To"] = email
        message.set_content(
            "We received a request to reset your BizPilot AI password.\n\n"
            f"Open this link to choose a new password:\n{reset_link}\n\n"
            "The link expires soon and can be used once. "
            "If you did not request this, you can ignore this email.\n"
        )
        return message

    def send_message(self, message: EmailMessage) -> None:
        cfg = self._settings
        context = ssl.create_default_context()
        if cfg.smtp_security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                cfg.smtp_host, cfg.smtp_port, timeout=cfg.timeout_seconds, context=context
            )
        else:
            client = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=cfg.timeout_seconds)
        with client:
            if cfg.smtp_security == "starttls":
                client.starttls(context=context)
            if cfg.smtp_username and cfg.smtp_password is not None:
                client.login(cfg.smtp_username, cfg.smtp_password.get_secret_value())
            client.send_message(message)

    async def deliver_password_reset_token(
        self,
        email: str,
        reset_token: str,
    ) -> None:
        message = self.build_message(email, reset_token)
        future = asyncio.get_running_loop().run_in_executor(None, self.send_message, message)
        self._pending.add(future)
        future.add_done_callback(self._on_sent)

    def _on_sent(self, future: asyncio.Future[None]) -> None:
        self._pending.discard(future)
        exc = None if future.cancelled() else future.exception()
        if exc is not None:
            # Never log the token, link, or SMTP credentials.
            logger.error(
                "Password recovery email delivery failed",
                extra={"error_type": type(exc).__name__},
            )

    async def wait_for_pending(self) -> None:
        """Await in-flight sends (used by tests and graceful shutdown)."""
        if self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)


def build_delivery_adapter(settings: Settings) -> PasswordResetDeliveryAdapter:
    """Select SMTP delivery when configured; otherwise the local development logger."""
    if settings.email.smtp_enabled:
        return SmtpPasswordResetDeliveryAdapter(settings.email)
    return DevelopmentLoggingPasswordResetDeliveryAdapter()


_global_delivery_adapter: Optional[PasswordResetDeliveryAdapter] = None


def get_delivery_adapter() -> PasswordResetDeliveryAdapter:
    """Get the active password reset delivery adapter."""
    global _global_delivery_adapter
    if _global_delivery_adapter is None:
        _global_delivery_adapter = build_delivery_adapter(get_settings())
    return _global_delivery_adapter


def set_delivery_adapter(adapter: PasswordResetDeliveryAdapter) -> None:
    """Override the active delivery adapter (used for testing)."""
    global _global_delivery_adapter
    _global_delivery_adapter = adapter


class PasswordRecoveryService:
    """Orchestrates password recovery requests and reset completions."""

    def __init__(
        self,
        session: AsyncSession,
        repository: Optional[AuthRepository] = None,
        password_service: Optional[PasswordService] = None,
        account_policy: Optional[AccountPolicyService] = None,
        delivery_adapter: Optional[PasswordResetDeliveryAdapter] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)
        self._password_service = password_service or PasswordService(settings)
        self._account_policy = account_policy or AccountPolicyService()
        self._delivery_adapter = delivery_adapter or get_delivery_adapter()
        cfg = settings or get_settings()
        self._ttl_minutes = cfg.auth.password_reset_token_minutes

    async def request_password_reset(
        self,
        request: ForgotPasswordRequest,
    ) -> ForgotPasswordResponse:
        """Process a forgot-password request with strict non-enumeration."""
        email_normalized = request.email.strip().lower()
        now = datetime.now(timezone.utc)

        # 1. Non-locking lookup to check user existence and status
        user = await self._repository.get_user_by_email(email_normalized)

        # Strict non-enumeration: unknown, disabled, or pending accounts return uniform response
        if user is None or user.status != UserStatus.ACTIVE.value:
            # Timing mitigation: execute comparable cryptographic dummy work
            self._password_service.verify_dummy()
            return ForgotPasswordResponse()

        raw_token: Optional[str] = None
        recipient_email: Optional[str] = None

        # 2. Durable token creation inside savepoint
        try:
            async with self._session.begin_nested():
                # Acquire row-level lock on the User entity to serialize concurrent recovery requests
                await self._repository.get_user_by_id_for_update(user.id)

                # Founder Decision 3: Invalidate all previous unconsumed reset tokens for this user
                await self._repository.invalidate_active_password_reset_tokens(user.id, now)

                # Generate new secure random token
                raw_token = generate_password_reset_token()
                token_hash = hash_password_reset_token(raw_token)
                expires_at = now + timedelta(minutes=self._ttl_minutes)

                await self._repository.create_password_reset_token(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
                recipient_email = user.email_normalized
        except Exception:
            raise

        # 3. Separate durable token creation from delivery adapter invocation.
        # Delivery errors must not change the uniform response (non-enumeration).
        if raw_token is not None and recipient_email is not None:
            try:
                await self._delivery_adapter.deliver_password_reset_token(
                    recipient_email,
                    raw_token,
                )
            except Exception as exc:
                logger.error(
                    "Password recovery delivery dispatch failed",
                    extra={"error_type": type(exc).__name__},
                )

        return ForgotPasswordResponse()

    async def reset_password(
        self,
        request: ResetPasswordRequest,
    ) -> ResetPasswordResponse:
        """Redeem a valid reset token and atomically update credentials and revoke sessions."""
        raw_token = request.token.strip()
        new_password = request.new_password
        token_hash = hash_password_reset_token(raw_token)
        now = datetime.now(timezone.utc)

        try:
            async with self._session.begin_nested():
                # Step 1: Lock PasswordResetToken row under database row-level locking
                token = await self._repository.get_password_reset_token_by_hash_for_update(token_hash)
                if token is None or token.consumed_at is not None or token.expires_at <= now:
                    raise AuthenticationException("Invalid or expired password reset token")

                # Step 2: Fetch associated user (read-only; no lock on users to prevent deadlock with refresh)
                user = await self._repository.get_user_by_id(token.user_id)
                if user is None:
                    raise AuthenticationException("Invalid or expired password reset token")

                # Step 3: Verify account eligibility
                try:
                    self._account_policy.verify_user_can_authenticate(user)
                except AuthenticationException:
                    raise AuthenticationException("Invalid or expired password reset token")

                # Step 4: Fetch current credential
                credential = await self._repository.get_credential_by_user_id(user.id)
                if credential is None:
                    raise AuthenticationException("Invalid or expired password reset token")

                # Step 6: Validate password policy
                self._password_service.validate_password_policy(new_password)

                # Step 7: Founder Decision 4: New password must NOT equal current password
                verify_res = self._password_service.verify_password(new_password, credential.password_hash)
                if verify_res.valid:
                    raise ValidationException("New password cannot be the same as your current password")

                # Step 8: Hash new password using Argon2id
                new_password_hash = self._password_service.hash_password(new_password)

                # Step 9: Update credential password_hash and password_updated_at
                await self._repository.update_password_hash(user.id, new_password_hash)

                # Step 10: Consume reset token permanently
                await self._repository.consume_password_reset_token(token.id, now)

                # Step 11: Revoke ALL active refresh sessions for this user
                await self._repository.revoke_all_user_refresh_tokens(user.id, now)
        except (AuthenticationException, ValidationException):
            raise
        except Exception:
            raise

        return ResetPasswordResponse()

"""Unit tests for SMTP password-reset delivery (FIX-004)."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

import pytest

from app.core.config import EmailSettings, Settings
from app.modules.auth import recovery
from app.modules.auth.recovery import (
    DevelopmentLoggingPasswordResetDeliveryAdapter,
    SmtpPasswordResetDeliveryAdapter,
    build_delivery_adapter,
)

TOKEN = "raw-reset-token-abc_123"
SMTP_SECRET = "Sm7p_Relay_Credential_2026_Long"


def _email_settings(**overrides: Any) -> EmailSettings:
    data: dict[str, Any] = {
        "smtp_host": "smtp.mail.invalid",
        "smtp_port": 587,
        "smtp_username": "bizpilot-mailer",
        "smtp_password": SMTP_SECRET,
        "from_address": "no-reply@bizpilot.invalid",
        "frontend_base_url": "https://app.bizpilot.invalid/",
    }
    data.update(overrides)
    return EmailSettings(**data)


class FakeSMTP:
    instances: list["FakeSMTP"] = []
    fail_on_send = False

    def __init__(self, host: str, port: int, timeout: float, context: Any = None) -> None:
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.calls: list[str] = []
        self.sent: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        self.calls.append("quit")

    def starttls(self, context: Any = None) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append(f"login:{username}")
        assert password == SMTP_SECRET

    def send_message(self, message: EmailMessage) -> None:
        if FakeSMTP.fail_on_send:
            raise OSError("relay unavailable")
        self.calls.append("send")
        self.sent.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    FakeSMTP.instances = []
    FakeSMTP.fail_on_send = False
    monkeypatch.setattr(recovery.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(recovery.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def test_message_contains_reset_link_and_headers() -> None:
    adapter = SmtpPasswordResetDeliveryAdapter(_email_settings())
    message = adapter.build_message("owner@shop.invalid", TOKEN)
    assert message["To"] == "owner@shop.invalid"
    assert message["From"] == "no-reply@bizpilot.invalid"
    body = message.get_content()
    assert f"https://app.bizpilot.invalid/reset-password?token={TOKEN}" in body


@pytest.mark.asyncio
async def test_starttls_delivery_logs_in_and_sends() -> None:
    adapter = SmtpPasswordResetDeliveryAdapter(_email_settings())
    await adapter.deliver_password_reset_token("owner@shop.invalid", TOKEN)
    await adapter.wait_for_pending()

    smtp = FakeSMTP.instances[-1]
    assert (smtp.host, smtp.port) == ("smtp.mail.invalid", 587)
    assert smtp.calls == ["starttls", "login:bizpilot-mailer", "send", "quit"]
    assert smtp.sent[0]["To"] == "owner@shop.invalid"


@pytest.mark.asyncio
async def test_ssl_delivery_without_auth_skips_starttls_and_login() -> None:
    adapter = SmtpPasswordResetDeliveryAdapter(
        _email_settings(smtp_security="ssl", smtp_port=465, smtp_username=None, smtp_password=None)
    )
    await adapter.deliver_password_reset_token("owner@shop.invalid", TOKEN)
    await adapter.wait_for_pending()

    smtp = FakeSMTP.instances[-1]
    assert smtp.context is not None
    assert smtp.calls == ["send", "quit"]


@pytest.mark.asyncio
async def test_send_failure_is_logged_without_secrets(caplog: pytest.LogCaptureFixture) -> None:
    FakeSMTP.fail_on_send = True
    adapter = SmtpPasswordResetDeliveryAdapter(_email_settings())
    with caplog.at_level(logging.INFO):
        await adapter.deliver_password_reset_token("owner@shop.invalid", TOKEN)
        await adapter.wait_for_pending()

    assert "Password recovery email delivery failed" in caplog.text
    for record in caplog.records:
        rendered = f"{record.getMessage()} {record.__dict__}"
        assert TOKEN not in rendered
        assert SMTP_SECRET not in rendered


def test_adapter_requires_smtp_configuration() -> None:
    with pytest.raises(ValueError):
        SmtpPasswordResetDeliveryAdapter(EmailSettings())


def _settings(email: dict[str, Any]) -> Settings:
    return Settings(
        environment="test",
        database={"url": "postgresql://test_user:test_password@localhost/bizpilot_test"},
        auth={"signing_secret": "test-only-signing-secret"},
        email=email,
        _env_file=None,
    )


def test_build_delivery_adapter_selects_by_configuration() -> None:
    assert isinstance(build_delivery_adapter(_settings({})), DevelopmentLoggingPasswordResetDeliveryAdapter)
    smtp_settings = _settings(
        {"smtp_host": "smtp.mail.invalid", "from_address": "no-reply@bizpilot.invalid"}
    )
    assert isinstance(build_delivery_adapter(smtp_settings), SmtpPasswordResetDeliveryAdapter)

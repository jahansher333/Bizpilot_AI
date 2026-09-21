"""Unit tests for TokenService (AUTH-004)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import AuthenticationSettings, DatabaseSettings, EnvironmentMode, Settings
from app.core.errors import AuthenticationException
from app.modules.auth.tokens import TokenService


@pytest.fixture
def token_settings() -> Settings:
    return Settings(
        environment=EnvironmentMode.TEST,
        database=DatabaseSettings(
            url="postgresql://test_user:test_password@localhost/bizpilot_test"
        ),
        auth=AuthenticationSettings(
            signing_secret="primary-active-signing-secret-key-12345",
            previous_signing_secrets=[
                SecretStr("retired-rotation-secret-key-11111-long"),
                SecretStr("older-rotation-secret-key-22222-long"),
            ],
            jwt_issuer="bizpilot-api",
            jwt_audience="bizpilot-web",
            access_token_minutes=15,
        ),
    )


@pytest.fixture
def token_service(token_settings: Settings) -> TokenService:
    return TokenService(token_settings)


def test_issue_access_token_success(token_service: TokenService) -> None:
    user_id = uuid.uuid4()
    result = token_service.issue_access_token(user_id)

    assert result.token
    assert result.expires_in == 900
    assert token_service.ttl_seconds == 900

    payload = token_service.decode_access_token(result.token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["iss"] == "bizpilot-api"
    assert payload["aud"] == "bizpilot-web"
    assert "jti" in payload
    assert payload["exp"] - payload["iat"] == 900


def test_issue_tokens_unique_jti(token_service: TokenService) -> None:
    user_id = uuid.uuid4()
    token1 = token_service.issue_access_token(user_id)
    token2 = token_service.issue_access_token(user_id)

    p1 = token_service.decode_access_token(token1.token)
    p2 = token_service.decode_access_token(token2.token)

    assert p1["jti"] != p2["jti"]
    # Check that jti is valid uuid
    uuid.UUID(p1["jti"])
    uuid.UUID(p2["jti"])


def test_token_contains_no_sensitive_or_tenant_claims(token_service: TokenService) -> None:
    user_id = uuid.uuid4()
    result = token_service.issue_access_token(user_id)
    payload = token_service.decode_access_token(result.token)

    for forbidden in ("email", "password", "hash", "role", "organization_id", "display_name", "permissions"):
        assert forbidden not in payload


def test_key_rotation_fallback_to_previous_secrets(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    user_id = uuid.uuid4()

    # Craft token using retired secret 1
    retired_secret = "retired-rotation-secret-key-11111-long"

    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    token_from_old_key = jwt.encode(raw_payload, retired_secret, algorithm="HS256")

    # Service should decode successfully using fallback to previous_signing_secrets
    decoded = service.decode_access_token(token_from_old_key)
    assert decoded["sub"] == str(user_id)


def test_token_with_unknown_signature_rejected(token_service: TokenService) -> None:
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    unknown_token = jwt.encode(raw_payload, "completely-unknown-secret-key-32-bytes-long", algorithm="HS256")


    with pytest.raises(AuthenticationException, match="Invalid authentication token"):
        token_service.decode_access_token(unknown_token)


def test_expired_token_rejected(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    user_id = uuid.uuid4()
    past = datetime.now(timezone.utc) - timedelta(minutes=20)
    raw_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int((past - timedelta(minutes=15)).timestamp()),
        "nbf": int((past - timedelta(minutes=15)).timestamp()),
        "exp": int(past.timestamp()),
    }
    expired_token = jwt.encode(
        raw_payload,
        token_settings.auth.signing_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationException, match="Authentication token has expired"):
        service.decode_access_token(expired_token)


def test_token_with_invalid_type_rejected(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "refresh",  # invalid token type
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    token = jwt.encode(
        raw_payload,
        token_settings.auth.signing_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationException, match="Invalid authentication token type"):
        service.decode_access_token(token)


def test_token_with_wrong_issuer_or_audience_rejected(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    secret = token_settings.auth.signing_secret.get_secret_value()

    # Wrong issuer
    bad_iss = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "wrong-issuer",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    with pytest.raises(AuthenticationException, match="Invalid authentication token"):
        service.decode_access_token(jwt.encode(bad_iss, secret, algorithm="HS256"))

    # Wrong audience
    bad_aud = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "wrong-aud",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    with pytest.raises(AuthenticationException, match="Invalid authentication token"):
        service.decode_access_token(jwt.encode(bad_aud, secret, algorithm="HS256"))


def test_token_with_alg_none_rejected(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    none_token = jwt.encode(raw_payload, key="", algorithm="none")

    with pytest.raises(AuthenticationException, match="Invalid authentication token"):
        service.decode_access_token(none_token)


def test_token_empty_or_malformed_rejected(token_service: TokenService) -> None:
    for bad in ("", "   ", "not-a-jwt", "a.b", "a.b.c.d"):
        with pytest.raises(AuthenticationException, match="Invalid authentication token"):
            token_service.decode_access_token(bad)


def test_token_invalid_sub_uuid_rejected(token_settings: Settings) -> None:
    service = TokenService(token_settings)
    now = datetime.now(timezone.utc)
    raw_payload = {
        "sub": "not-a-valid-uuid",
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iss": "bizpilot-api",
        "aud": "bizpilot-web",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    token = jwt.encode(
        raw_payload,
        token_settings.auth.signing_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationException, match="Invalid authentication token subject"):
        service.decode_access_token(token)

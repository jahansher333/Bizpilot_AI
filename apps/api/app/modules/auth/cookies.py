"""Refresh-token cookie transport and the origin check for cookie-authenticated endpoints (SEC-P1 F3).

The refresh token never appears in a response body: it travels only in an HttpOnly, Secure,
SameSite=Strict cookie scoped to /api/auth, so page scripts (and any injected script) cannot read
it. The short-lived access token is returned in the body and kept in memory by the web client.

SameSite=Strict stops cross-site requests from carrying the cookie, but sibling subdomains of the
same site still count as same-site. Endpoints that act on the cookie therefore also reject any
browser request whose Origin is not one of the configured CORS origins.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request, Response

from app.core.errors import AuthorizationException

REFRESH_COOKIE_NAME = "bizpilot_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def set_refresh_cookie(response: Response, raw_token: str, expires_at: datetime) -> None:
    """Attach the refresh token cookie; it lives exactly as long as its token family."""
    max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        raw_token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def read_refresh_cookie(request: Request) -> str | None:
    value = request.cookies.get(REFRESH_COOKIE_NAME)
    return value if value and value.strip() else None


def require_trusted_origin(request: Request) -> None:
    """Reject browser requests from origins outside the CORS allow-list.

    Browsers always send Origin on cross-origin and same-origin POSTs; requests without one come
    from non-browser clients, which cannot be driven by a malicious page.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    settings = getattr(request.app.state, "settings", None)
    allowed = {o.strip().rstrip("/") for o in (settings.cors_origins if settings else [])}
    if origin.strip().rstrip("/") not in allowed:
        raise AuthorizationException("Request origin is not allowed")

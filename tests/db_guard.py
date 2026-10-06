"""Keeps the test suite off shared and cloud databases.

Tests create users, organizations and records, so they must only ever run against a disposable
local database. They read ``TEST_DATABASE_URL`` (environment first, then the repo-root
``.env``) and never the application's ``BIZPILOT_DATABASE__URL``, which may point at a real
database. Any non-local host stops the run before a single test executes.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

TEST_DATABASE_ENV = "TEST_DATABASE_URL"

# Loopback addresses plus the docker-compose database service name.
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})

# Used when no test database is configured; DB-backed tests skip on these credentials.
PLACEHOLDER_DATABASE_URL = "postgresql://test_user:test_password@localhost/bizpilot_test"


class RemoteTestDatabaseError(RuntimeError):
    """Raised when the configured test database is not on this machine."""


def database_host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def resolve_test_database_url(environ: Mapping[str, str], dotenv: Mapping[str, str | None]) -> str | None:
    """The configured test database URL, or None. Never falls back to BIZPILOT_DATABASE__URL."""
    return environ.get(TEST_DATABASE_ENV) or dotenv.get(TEST_DATABASE_ENV) or None


def assert_local_database(url: str) -> None:
    host = database_host(url)
    if host not in LOCAL_DATABASE_HOSTS:
        raise RemoteTestDatabaseError(
            f"Refusing to run tests against database host '{host or '(none)'}'. "
            f"Tests write data, so {TEST_DATABASE_ENV} must point at a local, disposable database "
            f"(host one of: {', '.join(sorted(LOCAL_DATABASE_HOSTS))}). "
            "BIZPILOT_DATABASE__URL is never used by the test suite."
        )

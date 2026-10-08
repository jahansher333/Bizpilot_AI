"""The test suite must never write to a shared or cloud database (incident 2026-10-06)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.db_guard import (
    TEST_DATABASE_ENV,
    RemoteTestDatabaseError,
    assert_local_database,
    resolve_test_database_url,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@localhost/bizpilot_test",
        "postgresql://u:p@127.0.0.1:5432/bizpilot_test",
        "postgresql://u:p@[::1]/bizpilot_test",
        "postgresql://u:p@postgres:5432/bizpilot_dev",
    ],
)
def test_local_hosts_are_allowed(url: str) -> None:
    assert_local_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@ep-example-000000-pooler.c-1.us-east-1.aws.neon.tech/neondb?sslmode=require",
        "postgresql://u:p@db.example.com/bizpilot",
        "postgresql://u:p@10.0.0.5/bizpilot",
        "postgresql:///bizpilot",
    ],
)
def test_remote_or_hostless_urls_are_refused(url: str) -> None:
    with pytest.raises(RemoteTestDatabaseError, match="Refusing to run tests"):
        assert_local_database(url)


def test_application_database_url_is_never_used_for_tests() -> None:
    environ = {"BIZPILOT_DATABASE__URL": "postgresql://u:p@ep-x.neon.tech/neondb"}
    dotenv = {"BIZPILOT_DATABASE__URL": "postgresql://u:p@ep-x.neon.tech/neondb"}
    assert resolve_test_database_url(environ, dotenv) is None
    assert resolve_test_database_url({}, {TEST_DATABASE_ENV: "postgresql://u:p@localhost/t"}) == "postgresql://u:p@localhost/t"
    assert resolve_test_database_url({TEST_DATABASE_ENV: "postgresql://u:p@127.0.0.1/a"}, {TEST_DATABASE_ENV: "postgresql://u:p@localhost/b"}).endswith("/a")


def test_conftest_uses_the_guarded_url_not_the_shell_database_url() -> None:
    assert os.environ["BIZPILOT_DATABASE__URL"] == (os.environ.get(TEST_DATABASE_ENV) or os.environ["BIZPILOT_DATABASE__URL"])
    from urllib.parse import urlsplit

    assert urlsplit(os.environ["BIZPILOT_DATABASE__URL"]).hostname in {"localhost", "127.0.0.1", "::1", "postgres"}


def test_pytest_stops_before_any_test_when_the_test_database_is_remote() -> None:
    env = dict(os.environ, **{TEST_DATABASE_ENV: "postgresql://u:p@db.example.invalid/bizpilot"})
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/unit/test_app.py"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Refusing to run tests against database host 'db.example.invalid'" in output
    assert "test session starts" not in output and " collected" not in output

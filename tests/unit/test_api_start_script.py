"""The production entrypoint never trusts every proxy for X-Forwarded-For (SEC-P1 F1)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = REPO_ROOT / "apps" / "api" / "start.sh"
SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(SH is None, reason="POSIX sh is not available")


def _run(tmp_path: Path, forwarded_allow_ips: str | None) -> subprocess.CompletedProcess[str]:
    # A stub uvicorn records the arguments it is started with instead of serving.
    stub = tmp_path / "uvicorn"
    stub.write_text('#!/bin/sh\necho "uvicorn $*"\n', newline="\n")
    stub.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if key != "FORWARDED_ALLOW_IPS"}
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    if forwarded_allow_ips is not None:
        env["FORWARDED_ALLOW_IPS"] = forwarded_allow_ips
    script = START_SCRIPT.read_text().replace("\r\n", "\n")
    return subprocess.run([SH, "-c", script], env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("value", [None, "", "*", "10.0.0.0/8,*"])
def test_start_refuses_missing_or_wildcard_proxy_trust(tmp_path: Path, value: str | None) -> None:
    result = _run(tmp_path, value)
    assert result.returncode == 64
    assert "FORWARDED_ALLOW_IPS" in result.stderr
    assert "uvicorn" not in result.stdout


def test_start_passes_the_configured_ingress_range_to_uvicorn(tmp_path: Path) -> None:
    result = _run(tmp_path, "10.0.0.0/23,10.0.2.0/23")
    assert result.returncode == 0, result.stderr
    assert "--proxy-headers --forwarded-allow-ips 10.0.0.0/23,10.0.2.0/23" in result.stdout


def test_start_script_uses_lf_line_endings() -> None:
    assert b"\r\n" not in START_SCRIPT.read_bytes()


def test_api_image_has_no_wildcard_proxy_default() -> None:
    dockerfile = (REPO_ROOT / "apps" / "api" / "Dockerfile").read_text()
    assert 'FORWARDED_ALLOW_IPS="*"' not in dockerfile
    assert 'CMD ["/app/start.sh"]' in dockerfile

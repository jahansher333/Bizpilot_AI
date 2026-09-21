"""Unit tests verifying local Docker development configuration."""

from __future__ import annotations

from pathlib import Path
import yaml


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_docker_files_exist() -> None:
    root = get_repo_root()
    compose_file = root / "docker-compose.yml"
    dockerignore = root / ".dockerignore"
    api_dockerfile = root / "apps" / "api" / "Dockerfile.dev"
    web_dockerfile = root / "apps" / "web" / "Dockerfile.dev"
    setup_doc = root / "docs" / "development" / "LOCAL-SETUP.md"

    assert compose_file.exists(), "docker-compose.yml must exist"
    assert dockerignore.exists(), ".dockerignore must exist"
    assert api_dockerfile.exists(), "apps/api/Dockerfile.dev must exist"
    assert web_dockerfile.exists(), "apps/web/Dockerfile.dev must exist"
    assert setup_doc.exists(), "docs/development/LOCAL-SETUP.md must exist"


def test_docker_compose_structure() -> None:
    root = get_repo_root()
    compose_path = root / "docker-compose.yml"

    with compose_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "services" in data
    services = data["services"]

    # Verify required services
    assert "postgres" in services
    assert "api" in services
    assert "web" in services

    # Verify postgres configuration
    pg = services["postgres"]
    assert "image" in pg
    assert "postgres" in pg["image"]
    assert "healthcheck" in pg

    # Verify api configuration
    api = services["api"]
    assert "depends_on" in api
    assert "postgres" in api["depends_on"]
    assert "healthcheck" in api
    assert "environment" in api
    env = api["environment"]
    assert env["BIZPILOT_ENVIRONMENT"] == "local"

    # Verify web configuration
    web = services["web"]
    assert "depends_on" in web
    assert "api" in web["depends_on"]


def test_dockerignore_protects_sensitive_files() -> None:
    root = get_repo_root()
    dockerignore_path = root / ".dockerignore"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}

    assert ".env" in lines
    assert ".git" in lines
    assert "node_modules/" in lines
    assert "__pycache__/" in lines
    assert ".venv/" in lines

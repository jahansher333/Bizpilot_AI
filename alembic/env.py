"""Alembic environment configuration for BizPilot AI migrations.

This script configures Alembic to use the BizPilot settings for database URL
and the SQLAlchemy Base metadata for autogenerate support.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Add the API root to the path so we can import app modules
API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.modules.auth.models  # noqa: F401, E402
import app.modules.organizations.models  # noqa: F401, E402
import app.modules.trace.models  # noqa: F401, E402


config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from environment via Settings."""
    import os
    from dotenv import dotenv_values

    env_vals = dotenv_values(".env") if Path(".env").exists() else {}
    raw_url = os.environ.get("BIZPILOT_DATABASE__URL") or env_vals.get("BIZPILOT_DATABASE__URL") or ""
    auth_secret = os.environ.get("BIZPILOT_AUTH__SIGNING_SECRET") or env_vals.get("BIZPILOT_AUTH__SIGNING_SECRET") or "test-only-signing-secret"

    # Load settings which will validate configuration
    settings = Settings(
        environment="test",
        database={"url": raw_url},
        auth={"signing_secret": auth_secret},
        ai={"enabled": False},
        logging={"level": "INFO", "json_logs": False},
    )
    url = settings.database.url.get_secret_value()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = get_database_url()

    connectable: AsyncEngine = create_async_engine(
        url,
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_migrations_online())
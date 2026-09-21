"""SQLAlchemy engine creation and management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings


_engine: AsyncEngine | None = None


def normalize_database_url(raw_url: str) -> str:
    """Normalize database URL for async psycopg driver if needed."""
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create a new async SQLAlchemy engine from settings."""
    cfg = settings or get_settings()
    url = normalize_database_url(cfg.database.url.get_secret_value())
    return create_async_engine(
        url,
        poolclass=NullPool,
        future=True,
    )


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Get or create the global async engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings)
    return _engine


@asynccontextmanager
async def engine_lifespan(settings: Settings | None = None) -> AsyncGenerator[AsyncEngine, None]:
    """Async context manager for engine lifecycle (startup/shutdown)."""
    engine = create_engine(settings)
    try:
        yield engine
    finally:
        await engine.dispose()


async def dispose_engine() -> None:
    """Dispose the global engine if it exists."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
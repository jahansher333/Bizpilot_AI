"""SQLAlchemy async session factory and transaction management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import get_engine


class AsyncSessionFactory:
    """Factory for creating async database sessions."""

    def __init__(self) -> None:
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def configure(self) -> None:
        """Configure the sessionmaker with the global engine."""
        engine = get_engine()
        self._sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    def __call__(self) -> AsyncSession:
        """Create a new async session."""
        if self._sessionmaker is None:
            self.configure()
        return self._sessionmaker()


def get_session_factory() -> AsyncSessionFactory:
    """Get the global async session factory."""
    return AsyncSessionFactory()


@asynccontextmanager
async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on exception.
    """
    if sessionmaker is not None:
        session = sessionmaker()
    else:
        factory = get_session_factory()
        session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for request-scoped database session."""
    async with session_scope() as session:
        yield session
"""FastAPI application factory and lifecycle."""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.health import router as health_router
from app.api.router import build_api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationMiddleware
from app.db.engine import dispose_engine
from app.modules.auth import auth_router
from app.modules.organizations import organization_router

DEFAULT_MODULE_ROUTERS: tuple[APIRouter, ...] = (auth_router, organization_router)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.started = True
    try:
        yield
    finally:
        app.state.started = False
        await dispose_engine()


def create_app(
    settings: Settings | None = None,
    module_routers: Iterable[APIRouter] | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.logging)
    app = FastAPI(
        title="BizPilot API",
        debug=runtime_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.started = False

    # Middleware
    app.add_middleware(CorrelationMiddleware)

    # Exception handlers
    register_error_handlers(app)

    # Health and readiness probes
    app.include_router(health_router)

    # API module routers
    active_routers = DEFAULT_MODULE_ROUTERS if module_routers is None else module_routers
    app.include_router(build_api_router(active_routers))
    return app


app = create_app()
"""Central router registry for approved backend modules."""

from collections.abc import Iterable

from fastapi import APIRouter


def build_api_router(module_routers: Iterable[APIRouter] = ()) -> APIRouter:
    router = APIRouter(prefix="/api")
    for module_router in module_routers:
        router.include_router(module_router)
    return router
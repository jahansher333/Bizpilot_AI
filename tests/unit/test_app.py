from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.dependencies import RequestContext, get_request_context


def test_application_starts_and_stops(test_app) -> None:
    assert test_app.state.started is False
    with TestClient(test_app):
        assert test_app.state.started is True
    assert test_app.state.started is False


def test_openapi_smoke(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "BizPilot API"


def test_router_registry_has_no_business_routes(test_app) -> None:
    paths = {route.path for route in test_app.routes}
    assert paths == {
        "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc",
        "/healthz", "/health", "/readyz", "/ready",
    }
    assert not any(path.startswith("/api/") for path in paths)


def test_unknown_business_route_is_not_exposed(client) -> None:
    assert client.get("/api/orders").status_code == 404


def test_request_context_does_not_trust_client_tenant_header() -> None:
    class State:
        pass

    class Request:
        state = State()
        headers = {"x-organization-id": "attacker-controlled"}

    assert get_request_context(Request()) == RequestContext()

def test_module_router_registration(test_settings) -> None:
    module_router = APIRouter(prefix="/foundation-probe")

    @module_router.get("")
    def probe() -> dict[str, str]:
        return {"status": "registered"}

    from app.main import create_app

    app = create_app(test_settings, module_routers=[module_router])
    with TestClient(app) as registered_client:
        response = registered_client.get("/api/foundation-probe")
    assert response.status_code == 200
    assert response.json() == {"status": "registered"}
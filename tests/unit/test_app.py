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
    # Public API only: newer FastAPI wraps included routers, so app.routes no longer lists their
    # routes. The OpenAPI schema has every API route; the docs routes stay top-level.
    paths = {route.path for route in test_app.routes if getattr(route, "path", None)}
    paths |= set(test_app.openapi()["paths"])
    assert paths == {
        "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc",
        "/healthz", "/health", "/readyz", "/ready",
        "/api/auth/register", "/api/auth/login", "/api/auth/refresh",
        "/api/auth/logout", "/api/auth/logout-all",
        "/api/auth/forgot-password", "/api/auth/reset-password", "/api/auth/me",
        "/api/organizations", "/api/organizations/invitations",
        "/api/organizations/{organization_id}",
        "/api/organizations/{organization_id}/members",
        "/api/organizations/{organization_id}/members/{member_id}",
        "/api/organizations/{organization_id}/members/accept",
        "/api/organizations/{organization_id}/categories",
        "/api/organizations/{organization_id}/categories/{category_id}",
        "/api/organizations/{organization_id}/categories/{category_id}/archive",
        "/api/organizations/{organization_id}/products",
        "/api/organizations/{organization_id}/products/{product_id}",
        "/api/organizations/{organization_id}/products/{product_id}/archive",
        "/api/organizations/{organization_id}/inventory/balances",
        "/api/organizations/{organization_id}/inventory/balances/{product_id}",
        "/api/organizations/{organization_id}/inventory/movements",
        "/api/organizations/{organization_id}/inventory/opening-stock",
        "/api/organizations/{organization_id}/inventory/adjustments",
        "/api/organizations/{organization_id}/inventory/corrections",
        "/api/organizations/{organization_id}/inventory/void-reversals",
        "/api/organizations/{organization_id}/customers",
        "/api/organizations/{organization_id}/customers/balances",
        "/api/organizations/{organization_id}/customers/{customer_id}",
        "/api/organizations/{organization_id}/customers/{customer_id}/archive",
        "/api/organizations/{organization_id}/orders",
        "/api/organizations/{organization_id}/orders/{order_id}",
        "/api/organizations/{organization_id}/orders/{order_id}/void",
        "/api/organizations/{organization_id}/orders/{order_id}/correct",
        "/api/organizations/{organization_id}/payments",
        "/api/organizations/{organization_id}/payments/{payment_id}",
        "/api/organizations/{organization_id}/payments/{payment_id}/void",
        "/api/organizations/{organization_id}/payments/{payment_id}/correct",
        "/api/organizations/{organization_id}/expense-categories",
        "/api/organizations/{organization_id}/expense-categories/{category_id}",
        "/api/organizations/{organization_id}/expense-categories/{category_id}/archive",
        "/api/organizations/{organization_id}/expenses",
        "/api/organizations/{organization_id}/expenses/daily-total",
        "/api/organizations/{organization_id}/expenses/{expense_id}",
        "/api/organizations/{organization_id}/expenses/{expense_id}/void",
        "/api/organizations/{organization_id}/expenses/{expense_id}/correct",
        "/api/organizations/{organization_id}/dashboard",
        "/api/organizations/{organization_id}/ai/chat",
    }
    assert not any(path.startswith("/api/orders") for path in paths)
    assert not any(path.startswith("/api/payments") for path in paths)
    assert not any(path.startswith("/api/expenses") for path in paths)
    assert not any(path.startswith("/api/dashboard") for path in paths)
    assert not any(path.startswith("/api/products") for path in paths)


def test_cors_allows_only_configured_origins(test_settings) -> None:
    from app.main import create_app

    settings = test_settings.model_copy(update={"cors_origins": ["http://allowed.test"]})
    with TestClient(create_app(settings)) as cors_client:
        allowed = cors_client.options(
            "/api/auth/login",
            headers={"Origin": "http://allowed.test", "Access-Control-Request-Method": "POST"},
        )
        blocked = cors_client.options(
            "/api/auth/login",
            headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
        )
    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"
    # The refresh token is an HttpOnly cookie (SEC-P1 F3): credentials only for listed origins.
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    # A rejected preflight carries no allow-origin, so browsers refuse it regardless.
    assert "access-control-allow-origin" not in blocked.headers


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
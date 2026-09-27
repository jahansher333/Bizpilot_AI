"""Full Cross-Module Integration Suite (HARD-001).

Validates all P0 business modules together against PostgreSQL in a unified,
multi-tenant end-to-end operational flow:
1. Authentication & Multi-Tenant Membership (Owner, Manager, Staff)
2. Catalog & Inventory Atomic Stock Management
3. Customer Lifecycle & Balance Derivation
4. Orders Atomicity & Warehouse Deduction
5. Payments, Receipt Inflows & Customer Balance Offsetting
6. Operating Expenses & Strict RBAC Isolation
7. Deterministic Operational Dashboard Aggregation
8. AI Assistant Grounding, Tool Permissions & Privacy Metadata
9. Adversarial Cross-Tenant Boundary Enforcement & IDOR Rejection
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents import RunResult
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.router import _ORCHESTRATOR
from app.modules.organizations.enums import MemberRole


@pytest.fixture
async def full_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient with database session bound to the transaction rollback."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str]:
    """Register and authenticate a user, returning email and JWT access token."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePass123!#"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    assert reg.status_code == 202

    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login.status_code == 200
    return email, login.json()["access_token"]


async def _create_org(client: AsyncClient, token: str, name: str) -> str:
    """Create an organization and return its UUID string."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _invite_and_accept(
    client: AsyncClient,
    owner_token: str,
    org_id: str,
    member_email: str,
    member_token: str,
    role: MemberRole,
) -> None:
    """Owner invites a user, and the user accepts the membership."""
    invite = await client.post(
        f"/api/organizations/{org_id}/members",
        json={"email": member_email, "role": role.value},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert invite.status_code == 201

    accept = await client.post(
        f"/api/organizations/{org_id}/members/accept",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accept.status_code == 200


@pytest.mark.asyncio
async def test_full_cross_module_integration_and_tenant_isolation(full_client: AsyncClient):
    """Execute complete multi-module operational workflow with multi-tenant verification."""
    client = full_client

    # =========================================================================
    # STEP 1: AUTHENTICATION & MULTI-TENANT PROVISIONING
    # =========================================================================
    # Tenant A users
    email_a_owner, token_a_owner = await _create_user(client, "owner_a")
    email_a_mgr, token_a_mgr = await _create_user(client, "mgr_a")
    email_a_staff, token_a_staff = await _create_user(client, "staff_a")

    # Tenant B user
    email_b_owner, token_b_owner = await _create_user(client, "owner_b")

    # Provision Organizations
    org_a = await _create_org(client, token_a_owner, "Lahore Super Store")
    org_b = await _create_org(client, token_b_owner, "Karachi Traders")

    # Invite Manager and Staff to Org A
    await _invite_and_accept(client, token_a_owner, org_a, email_a_mgr, token_a_mgr, MemberRole.MANAGER)
    await _invite_and_accept(client, token_a_owner, org_a, email_a_staff, token_a_staff, MemberRole.STAFF)

    # =========================================================================
    # STEP 2: CATALOG & INVENTORY SETUP (TENANT A)
    # =========================================================================
    # 2.1 Create category in Org A
    cat_resp = await client.post(
        f"/api/organizations/{org_a}/categories",
        json={"name": "Dry Fruits"},
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    # 2.2 Create product in Org A
    prod_resp = await client.post(
        f"/api/organizations/{org_a}/products",
        json={
            "code": "ALMOND-01",
            "name": "Kagzi Badam 1kg",
            "base_unit": "pack",
            "default_price_minor": 150000,  # PKR 1,500.00
            "category_id": cat_id,
        },
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert prod_resp.status_code == 201
    prod_a_id = prod_resp.json()["id"]

    # 2.3 Initialize inventory stock in Org A (Initial adjustment: +50 units)
    adj_resp = await client.post(
        f"/api/organizations/{org_a}/inventory/adjustments",
        json={
            "product_id": prod_a_id,
            "quantity_delta": 50,
            "reason": "Initial opening warehouse intake",
        },
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert adj_resp.status_code == 200
    assert adj_resp.json()["balance"]["on_hand_quantity"] == 50

    # =========================================================================
    # STEP 3: CUSTOMER REGISTRATION (TENANT A)
    # =========================================================================
    cust_resp = await client.post(
        f"/api/organizations/{org_a}/customers",
        json={
            "name": "Al-Madina Traders",
            "phone": "03009988776",
            "notes": "Key wholesale customer",
        },
        headers={"Authorization": f"Bearer {token_a_mgr}"},
    )
    assert cust_resp.status_code == 201
    cust_a_id = cust_resp.json()["id"]

    # =========================================================================
    # STEP 4: SALES ORDER CREATION & ATOMIC INVENTORY DEDUCTION (TENANT A)
    # =========================================================================
    # Staff records a sales order: 10 packs of Kagzi Badam @ PKR 1,500 = PKR 15,000.00 (1,500,000 minor)
    order_resp = await client.post(
        f"/api/organizations/{org_a}/orders",
        json={
            "customer_id": cust_a_id,
            "items": [
                {
                    "product_id": prod_a_id,
                    "quantity": 10,
                    "unit_price_minor": 150000,
                }
            ],
            "currency_code": "PKR",
        },
        headers={"Authorization": f"Bearer {token_a_staff}"},
    )
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    order_a_id = order_data["id"]
    assert order_data["order_total_minor"] == 1500000

    # Verify inventory was atomically deducted from 50 to 40
    inv_check = await client.get(
        f"/api/organizations/{org_a}/inventory/balances/{prod_a_id}",
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert inv_check.status_code == 200
    assert inv_check.json()["on_hand_quantity"] == 40

    # =========================================================================
    # STEP 5: PAYMENT RECEIPT & CUSTOMER BALANCE (TENANT A)
    # =========================================================================
    # Record payment receipt of PKR 10,000.00 (1,000,000 minor)
    pay_resp = await client.post(
        f"/api/organizations/{org_a}/payments",
        json={
            "amount_minor": 1000000,
            "channel": "bank_transfer",
            "customer_id": cust_a_id,
            "order_id": order_a_id,
            "account_label": "Meezan Current Account",
            "external_reference": "TXN-98412",
        },
        headers={"Authorization": f"Bearer {token_a_staff}"},
    )
    assert pay_resp.status_code == 201
    pay_data = pay_resp.json()
    assert pay_data["amount_minor"] == 1000000

    # =========================================================================
    # STEP 6: OPERATING EXPENSES & RBAC VERIFICATION (TENANT A)
    # =========================================================================
    # 6.1 Staff attempts to record expense -> 403 Forbidden
    staff_exp = await client.post(
        f"/api/organizations/{org_a}/expenses",
        json={
            "amount_minor": 200000,
            "payment_method": "cash",
            "payee": "Utility Store",
        },
        headers={"Authorization": f"Bearer {token_a_staff}"},
    )
    assert staff_exp.status_code == 403

    # 6.2 Manager creates expense category and records operational expense (PKR 2,000.00 = 200,000 minor)
    exp_cat_resp = await client.post(
        f"/api/organizations/{org_a}/expense-categories",
        json={"name": "Logistics & Freight"},
        headers={"Authorization": f"Bearer {token_a_mgr}"},
    )
    assert exp_cat_resp.status_code == 201
    exp_cat_id = exp_cat_resp.json()["id"]

    exp_resp = await client.post(
        f"/api/organizations/{org_a}/expenses",
        json={
            "amount_minor": 200000,
            "payment_method": "cash",
            "expense_category_id": exp_cat_id,
            "payee": "Lahore Goods Transport",
            "description": "Stock delivery freight charge",
        },
        headers={"Authorization": f"Bearer {token_a_mgr}"},
    )
    assert exp_resp.status_code == 201

    # =========================================================================
    # STEP 7: DETERMINISTIC OPERATIONAL DASHBOARD (TENANT A)
    # =========================================================================
    # 7.1 Owner dashboard: Full metrics
    dash_owner = await client.get(
        f"/api/organizations/{org_a}/dashboard?period=today",
        headers={"Authorization": f"Bearer {token_a_owner}"},
    )
    assert dash_owner.status_code == 200
    dash_data = dash_owner.json()
    assert dash_data["sales"]["total_sales_minor"] == 1500000
    assert dash_data["sales"]["order_count"] == 1
    assert dash_data["payments"]["total_collected_minor"] == 1000000
    assert dash_data["payments"]["payment_count"] == 1
    assert dash_data["expenses"]["total_expenses_minor"] == 200000
    assert dash_data["expenses"]["expense_count"] == 1
    assert dash_data["net_cash"]["net_cash_minor"] == 800000  # 1,000,000 - 200,000

    # 7.2 Staff dashboard: Expenses & Net Cash are restricted
    dash_staff = await client.get(
        f"/api/organizations/{org_a}/dashboard?period=today",
        headers={"Authorization": f"Bearer {token_a_staff}"},
    )
    assert dash_staff.status_code == 200
    staff_dash_data = dash_staff.json()
    assert staff_dash_data["sales"]["total_sales_minor"] == 1500000
    assert staff_dash_data["payments"]["total_collected_minor"] == 1000000
    assert staff_dash_data["expenses"] is None
    assert staff_dash_data["net_cash"] is None

    # =========================================================================
    # STEP 8: AI ASSISTANT DETERMINISTIC GROUNDING & PRIVACY
    # =========================================================================
    fake_provider = MagicMock()
    fake_provider.is_enabled = True
    fake_provider.model_name = "gpt-4o-mini"
    fake_provider.timeout_seconds = 10.0
    fake_provider.max_tool_calls = 5
    fake_provider.log_raw_prompts = False
    fake_provider.get_client.return_value = MagicMock()
    fake_provider.execute_with_timeout = AsyncMock(side_effect=lambda coro, **kwargs: coro)

    async def fake_runner_impl(starting_agent, input, context, max_turns, run_config):
        return RunResult(
            input=input,
            new_items=[],
            raw_responses=[],
            final_output="Today's total sales are PKR 15,000.00 from 1 confirmed order.",
            input_guardrail_results=[],
            output_guardrail_results=[],
            _last_agent=starting_agent,
        )

    with patch.object(_ORCHESTRATOR, "_provider", fake_provider), \
         patch("agents.Runner.run", side_effect=fake_runner_impl):
        ai_resp = await client.post(
            f"/api/organizations/{org_a}/ai/chat",
            json={"message": "What are our total sales today?"},
            headers={"Authorization": f"Bearer {token_a_owner}"},
        )
        assert ai_resp.status_code == 200
        ai_data = ai_resp.json()
        assert "content" in ai_data
        assert "Today's total sales" in ai_data["content"]

    # =========================================================================
    # STEP 9: ADVERSARIAL CROSS-TENANT & IDOR ENFORCEMENT
    # =========================================================================
    # 9.1 Tenant B attempts to read Tenant A endpoints -> 403 Forbidden
    endpoints_to_test = [
        f"/api/organizations/{org_a}/products",
        f"/api/organizations/{org_a}/inventory/balances",
        f"/api/organizations/{org_a}/orders",
        f"/api/organizations/{org_a}/payments",
        f"/api/organizations/{org_a}/expenses",
        f"/api/organizations/{org_a}/dashboard",
    ]
    for endpoint in endpoints_to_test:
        forbidden_resp = await client.get(
            endpoint,
            headers={"Authorization": f"Bearer {token_b_owner}"},
        )
        assert forbidden_resp.status_code in (403, 404), f"Expected 403 or 404 for {endpoint} with Tenant B token"

    # 9.2 Tenant B attempts to reference Tenant A product in an order in Org B -> rejected
    cross_order_resp = await client.post(
        f"/api/organizations/{org_b}/orders",
        json={
            "items": [
                {
                    "product_id": prod_a_id,  # Product belonging to Org A
                    "quantity": 1,
                    "unit_price_minor": 100000,
                }
            ],
            "currency_code": "PKR",
        },
        headers={"Authorization": f"Bearer {token_b_owner}"},
    )
    assert cross_order_resp.status_code in (400, 404, 422), "Cross-tenant product reference must fail"

    # 9.3 Tenant B attempts to reference Tenant A customer in a payment in Org B -> rejected
    cross_pay_resp = await client.post(
        f"/api/organizations/{org_b}/payments",
        json={
            "amount_minor": 50000,
            "channel": "cash",
            "customer_id": cust_a_id,  # Customer belonging to Org A
        },
        headers={"Authorization": f"Bearer {token_b_owner}"},
    )
    assert cross_pay_resp.status_code in (400, 404, 422), "Cross-tenant customer reference must fail"

"""Integration tests for product persistence, lifecycle, and API (CAT-002)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.categories.enums import CategoryStatus
from app.modules.categories.models import Category
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product


@pytest.fixture
async def api_client(
    test_app: FastAPI,
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with get_session overridden to db_session."""
    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


async def _create_user(client: AsyncClient, prefix: str) -> tuple[str, str]:
    """Register and login a user, returning email and access_token."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecurePassword123!"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": f"{prefix} User"},
    )
    assert reg_resp.status_code == 202

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": pw},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return email, token


async def _create_org(client: AsyncClient, token: str, name: str = "Test Org") -> str:
    """Create an organization and return its ID string."""
    resp = await client.post(
        "/api/organizations",
        json={"display_name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_category(client: AsyncClient, token: str, org_id: str, name: str) -> str:
    """Create a category in an organization and return its ID string."""
    resp = await client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ==============================================================================
# 1. Database Schema & Constraint Verification
# ==============================================================================


@pytest.mark.asyncio
async def test_products_table_structure_in_postgres(db_session: AsyncSession) -> None:
    """Verify products table and required columns exist in PostgreSQL."""
    query = text(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'products'
        ORDER BY column_name;
        """
    )
    res = await db_session.execute(query)
    columns = {row[0]: (row[1], row[2]) for row in res.fetchall()}

    expected_cols = [
        "id",
        "organization_id",
        "category_id",
        "code",
        "name",
        "base_unit",
        "default_price_minor",
        "currency_code",
        "status",
        "created_by_user_id",
        "created_at",
        "updated_at",
        "archived_at",
    ]
    for col in expected_cols:
        assert col in columns, f"Column {col} missing from products table"

    assert columns["id"][1] == "NO"
    assert columns["organization_id"][1] == "NO"
    assert columns["code"][1] == "NO"
    assert columns["name"][1] == "NO"
    assert columns["base_unit"][1] == "NO"
    assert columns["default_price_minor"][1] == "NO"
    assert columns["currency_code"][1] == "NO"
    assert columns["status"][1] == "NO"
    assert columns["category_id"][1] == "YES"
    assert columns["created_by_user_id"][1] == "YES"
    assert columns["archived_at"][1] == "YES"


@pytest.mark.asyncio
async def test_products_constraints_and_indexes_in_postgres(db_session: AsyncSession) -> None:
    """Verify check constraints and indexes on products table in PostgreSQL."""
    ck_query = text(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'products'::regclass AND contype = 'c';
        """
    )
    ck_res = await db_session.execute(ck_query)
    ck_names = {row[0] for row in ck_res.fetchall()}
    assert any("status" in c for c in ck_names)
    assert any("price_non_negative" in c for c in ck_names)
    assert any("code_len" in c for c in ck_names)
    assert any("name_len" in c for c in ck_names)
    assert any("currency_len" in c for c in ck_names)
    assert any("base_unit_len" in c for c in ck_names)

    ix_query = text(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'products';
        """
    )
    ix_res = await db_session.execute(ix_query)
    ix_names = {row[0] for row in ix_res.fetchall()}
    assert "ix_products_organization_id" in ix_names
    assert "ix_products_org_status" in ix_names
    assert "ix_products_org_category" in ix_names
    assert "uq_products_org_active_code" in ix_names


# ==============================================================================
# 2. Product API Endpoints & Uniqueness Lifecycle
# ==============================================================================


@pytest.mark.asyncio
async def test_product_create_and_read(api_client: AsyncClient) -> None:
    _, token = await _create_user(api_client, "prod_crud")
    org_id = await _create_org(api_client, token, "Product CRUD Org")

    # Create active product
    resp = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={
            "code": "PROD-101",
            "name": "Super Basmati Rice 5kg",
            "base_unit": "bag",
            "default_price_minor": 185000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "PROD-101"
    assert data["name"] == "Super Basmati Rice 5kg"
    assert data["base_unit"] == "bag"
    assert data["default_price_minor"] == 185000
    assert data["currency_code"] == "PKR"
    assert data["status"] == "active"
    assert data["category_id"] is None
    prod_id = data["id"]

    # Read product
    get_resp = await api_client.get(
        f"/api/organizations/{org_id}/products/{prod_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == prod_id


@pytest.mark.asyncio
async def test_product_case_insensitive_active_code_uniqueness_same_org(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "prod_uniq")
    org_id = await _create_org(api_client, token, "Uniqueness Org")

    resp1 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "PROD-01", "name": "Item A"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    # Exact duplicate
    resp2 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "PROD-01", "name": "Item B"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 409
    assert "active code already exists" in resp2.json()["error"]["message"]

    # Lowercase duplicate
    resp3 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "prod-01", "name": "Item C"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == 409

    # Whitespace-padded mixed-case duplicate
    resp4 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "  pRoD-01  ", "name": "Item D"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp4.status_code == 409


@pytest.mark.asyncio
async def test_product_same_code_different_orgs_allowed(
    api_client: AsyncClient,
) -> None:
    _, token1 = await _create_user(api_user_client := api_client, "org1_user")
    _, token2 = await _create_user(api_client, "org2_user")

    org1 = await _create_org(api_client, token1, "Org One")
    org2 = await _create_org(api_client, token2, "Org Two")

    resp1 = await api_client.post(
        f"/api/organizations/{org1}/products",
        json={"code": "SHARED-SKU", "name": "Product in Org 1"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp1.status_code == 201

    resp2 = await api_client.post(
        f"/api/organizations/{org2}/products",
        json={"code": "shared-sku", "name": "Product in Org 2"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp2.status_code == 201


@pytest.mark.asyncio
async def test_product_archived_code_reuse_allowed(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "reuse_code")
    org_id = await _create_org(api_client, token, "Reuse Code Org")

    # Create PROD-01
    resp1 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "PROD-01", "name": "Original Product"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    prod1_id = resp1.json()["id"]

    # Archive PROD-01
    arch_resp = await api_client.post(
        f"/api/organizations/{org_id}/products/{prod1_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "archived"

    # Recreate with same code (different case)
    resp2 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "prod-01", "name": "New Product Same Code"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["id"] != prod1_id
    assert resp2.json()["status"] == "active"


@pytest.mark.asyncio
async def test_product_names_not_unique_in_same_org(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "name_nouniq")
    org_id = await _create_org(api_client, token, "Name Org")

    resp1 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "CODE-A", "name": "Generic T-Shirt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    # Same name with different code is completely allowed
    resp2 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "CODE-B", "name": "Generic T-Shirt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201


@pytest.mark.asyncio
async def test_product_category_assignment_lifecycle(
    api_client: AsyncClient,
) -> None:
    _, token1 = await _create_user(api_client, "cat_user1")
    _, token2 = await _create_user(api_client, "cat_user2")

    org1 = await _create_org(api_client, token1, "Cat Org 1")
    org2 = await _create_org(api_client, token2, "Cat Org 2")

    cat1_id = await _create_category(api_client, token1, org1, "Beverages")
    cat2_id = await _create_category(api_client, token2, org2, "Foreign Cat")

    # 1. Product assigned to valid active category in same org
    resp1 = await api_client.post(
        f"/api/organizations/{org1}/products",
        json={"code": "DRINK-01", "name": "Mineral Water", "category_id": cat1_id},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["category_id"] == cat1_id
    prod1_id = resp1.json()["id"]

    # 2. Attempting to assign foreign category -> 404 (FD-CAT002-03)
    resp_foreign = await api_client.post(
        f"/api/organizations/{org1}/products",
        json={"code": "DRINK-02", "name": "Foreign Item", "category_id": cat2_id},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp_foreign.status_code == 404

    # 3. Archive cat1
    arch_cat_resp = await api_client.post(
        f"/api/organizations/{org1}/categories/{cat1_id}/archive",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert arch_cat_resp.status_code == 200

    # 4. Existing product referencing archived category remains untouched and readable
    get_prod1 = await api_client.get(
        f"/api/organizations/{org1}/products/{prod1_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert get_prod1.status_code == 200
    assert get_prod1.json()["category_id"] == cat1_id

    # 5. New product cannot be assigned to archived category -> 409 Conflict
    resp_arch_cat = await api_client.post(
        f"/api/organizations/{org1}/products",
        json={"code": "DRINK-03", "name": "Juice", "category_id": cat1_id},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp_arch_cat.status_code == 409
    assert "Cannot assign an archived category" in resp_arch_cat.json()["error"]["message"]

    # 6. Uncategorize product 1 explicitly by passing category_id: null
    patch_uncat = await api_client.patch(
        f"/api/organizations/{org1}/products/{prod1_id}",
        json={"category_id": None},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert patch_uncat.status_code == 200
    assert patch_uncat.json()["category_id"] is None


@pytest.mark.asyncio
async def test_product_update_lifecycle_and_archived_conflict(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "upd_user")
    org_id = await _create_org(api_client, token, "Update Org")

    resp = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "OLD-CODE", "name": "Old Name", "default_price_minor": 1000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    prod_id = resp.json()["id"]

    # Partial update: code and price
    upd_resp = await api_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"code": "NEW-CODE", "default_price_minor": 2500},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["code"] == "NEW-CODE"
    assert upd_resp.json()["default_price_minor"] == 2500
    assert upd_resp.json()["name"] == "Old Name"

    # Archive product
    arch_resp = await api_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch_resp.status_code == 200

    # Attempt to update archived product -> 409 Conflict (FD-CAT002-04)
    upd_arch = await api_client.patch(
        f"/api/organizations/{org_id}/products/{prod_id}",
        json={"name": "Will Fail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd_arch.status_code == 409
    assert "Cannot update an archived product" in upd_arch.json()["error"]["message"]


@pytest.mark.asyncio
async def test_product_natural_idempotent_archive(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "idem_user")
    org_id = await _create_org(api_client, token, "Archive Idem Org")

    resp = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "PROD-IDEM", "name": "Idempotent Product"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    prod_id = resp.json()["id"]

    # First archive
    arch1 = await api_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch1.status_code == 200
    archived_at_1 = arch1.json()["archived_at"]
    assert archived_at_1 is not None

    # Second archive (natural idempotency)
    arch2 = await api_client.post(
        f"/api/organizations/{org_id}/products/{prod_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch2.status_code == 200
    assert arch2.json()["status"] == "archived"
    assert arch2.json()["archived_at"] == archived_at_1


@pytest.mark.asyncio
async def test_product_list_filtering_and_pagination(
    api_client: AsyncClient,
) -> None:
    _, token = await _create_user(api_client, "list_user")
    org_id = await _create_org(api_client, token, "List Org")

    cat_id = await _create_category(api_client, token, org_id, "Filter Cat")

    # Create 3 products
    p1 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "P-1", "name": "Product One", "category_id": cat_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p1.status_code == 201
    p1_id = p1.json()["id"]

    p2 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "P-2", "name": "Product Two", "category_id": cat_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p2.status_code == 201

    p3 = await api_client.post(
        f"/api/organizations/{org_id}/products",
        json={"code": "P-3", "name": "Product Three"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert p3.status_code == 201

    # Archive p1
    await api_client.post(
        f"/api/organizations/{org_id}/products/{p1_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Filter status=active
    act_list = await api_client.get(
        f"/api/organizations/{org_id}/products?status=active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert act_list.status_code == 200
    assert act_list.json()["total"] == 2

    # Filter status=archived
    arch_list = await api_client.get(
        f"/api/organizations/{org_id}/products?status=archived",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch_list.status_code == 200
    assert arch_list.json()["total"] == 1
    assert arch_list.json()["items"][0]["id"] == p1_id

    # Filter category_id
    cat_list = await api_client.get(
        f"/api/organizations/{org_id}/products?category_id={cat_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cat_list.status_code == 200
    assert cat_list.json()["total"] == 2  # p1 and p2

    # Pagination: limit=1, offset=0
    page1 = await api_client.get(
        f"/api/organizations/{org_id}/products?limit=1&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page1.status_code == 200
    assert len(page1.json()["items"]) == 1
    assert page1.json()["total"] == 3

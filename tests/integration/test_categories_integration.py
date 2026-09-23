"""Integration tests for category persistence, lifecycle, and API (CAT-001)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.models import User
from app.modules.categories.enums import CategoryStatus
from app.modules.categories.models import Category
from app.modules.organizations.models import Organization, OrganizationMember


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


# ==============================================================================
# 1. Database Schema & Constraint Verification
# ==============================================================================


@pytest.mark.asyncio
async def test_categories_table_structure_in_postgres(db_session: AsyncSession) -> None:
    """Verify categories table and required columns exist in PostgreSQL."""
    query = text(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'categories'
        ORDER BY ordinal_position;
        """
    )
    result = await db_session.execute(query)
    columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

    assert "id" in columns
    assert columns["id"][1] == "NO"
    assert "organization_id" in columns
    assert columns["organization_id"][1] == "NO"
    assert "name" in columns
    assert columns["name"][1] == "NO"
    assert "status" in columns
    assert columns["status"][1] == "NO"
    assert "created_by_user_id" in columns
    assert columns["created_by_user_id"][1] == "YES"
    assert "created_at" in columns
    assert columns["created_at"][1] == "NO"
    assert "updated_at" in columns
    assert columns["updated_at"][1] == "NO"
    assert "archived_at" in columns
    assert columns["archived_at"][1] == "YES"


@pytest.mark.asyncio
async def test_categories_check_constraints_enforced(db_session: AsyncSession) -> None:
    """Verify check constraints for status and name length at database level."""
    org = Organization(
        id=uuid.uuid4(),
        display_name="Constraint Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()

    # Invalid status
    bad_status_cat = Category(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Valid Name",
        status="deleted",
    )
    db_session.add(bad_status_cat)
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()
    assert "ck_categories_status" in str(exc_info.value).lower()
    await db_session.rollback()

    # Invalid name length (< 2 chars after trim)
    bad_name_cat = Category(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="  a  ",
        status="active",
    )
    db_session.add(bad_name_cat)
    with pytest.raises(IntegrityError) as exc_info2:
        await db_session.flush()
    assert "ck_categories_name_len" in str(exc_info2.value).lower()
    await db_session.rollback()


# ==============================================================================
# 2. FD-CAT001-01: Case-Insensitive Active Name Uniqueness
# ==============================================================================


@pytest.mark.asyncio
async def test_case_insensitive_active_name_uniqueness_same_org(
    api_client: AsyncClient,
) -> None:
    """Verify case-insensitive conflict within the same organization per FD-CAT001-01."""
    _, token = await _create_user(api_client, "owner_cat1")
    org_id = await _create_org(api_client, token, "Category Org 1")

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create initial category "Beverages"
    resp1 = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Beverages"},
        headers=headers,
    )
    assert resp1.status_code == 201
    assert resp1.json()["name"] == "Beverages"

    # 2. Attempt exact lowercase "beverages" -> 409 Conflict
    resp2 = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "beverages"},
        headers=headers,
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CONFLICT"

    # 3. Attempt uppercase with whitespace "  BEVERAGES  " -> 409 Conflict
    resp3 = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "  BEVERAGES  "},
        headers=headers,
    )
    assert resp3.status_code == 409
    assert resp3.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_active_name_uniqueness_isolated_across_different_orgs(
    api_client: AsyncClient,
) -> None:
    """Verify same category name is permitted across different organizations."""
    _, token1 = await _create_user(api_client, "owner_cat_org1")
    org_id_1 = await _create_org(api_client, token1, "Category Org Alpha")

    _, token2 = await _create_user(api_client, "owner_cat_org2")
    org_id_2 = await _create_org(api_client, token2, "Category Org Beta")

    # Create "Beverages" in Org Alpha
    resp1 = await api_client.post(
        f"/api/organizations/{org_id_1}/categories",
        json={"name": "Beverages"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp1.status_code == 201

    # Create same name "beverages" in Org Beta -> Must succeed
    resp2 = await api_client.post(
        f"/api/organizations/{org_id_2}/categories",
        json={"name": "beverages"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["organization_id"] == org_id_2


@pytest.mark.asyncio
async def test_archived_name_can_be_reused_by_new_active_category(
    api_client: AsyncClient,
) -> None:
    """Verify partial index: archiving a category frees the name for a new active category."""
    _, token = await _create_user(api_client, "owner_reuse")
    org_id = await _create_org(api_client, token, "Reuse Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create "Electronics"
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Electronics"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]

    # 2. Archive "Electronics"
    arch_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=headers,
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "archived"
    assert arch_resp.json()["archived_at"] is not None

    # 3. Create new active category with same name "electronics" -> Must succeed!
    reuse_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "electronics"},
        headers=headers,
    )
    assert reuse_resp.status_code == 201
    assert reuse_resp.json()["id"] != cat_id
    assert reuse_resp.json()["status"] == "active"


# ==============================================================================
# 3. Category Lifecycle & CRUD Flow via API
# ==============================================================================


@pytest.mark.asyncio
async def test_category_crud_and_lifecycle_flow(
    api_client: AsyncClient,
) -> None:
    """End-to-end test of category create, get, list, pagination, filter, update, archive."""
    _, token = await _create_user(api_client, "owner_lifecycle")
    org_id = await _create_org(api_client, token, "Lifecycle Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create categories
    cat1_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Bakery"},
        headers=headers,
    )
    assert cat1_resp.status_code == 201
    cat1 = cat1_resp.json()
    assert cat1["name"] == "Bakery"
    assert cat1["status"] == "active"
    assert cat1["created_by_user_id"] is not None
    assert cat1["archived_at"] is None

    cat2_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Dairy"},
        headers=headers,
    )
    assert cat2_resp.status_code == 201
    cat2 = cat2_resp.json()

    # 2. Get category by ID
    get_resp = await api_client.get(
        f"/api/organizations/{org_id}/categories/{cat1['id']}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cat1["id"]

    # 3. List categories with pagination
    list_resp = await api_client.get(
        f"/api/organizations/{org_id}/categories?limit=1&offset=0",
        headers=headers,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0

    # 4. Update category name
    update_resp = await api_client.patch(
        f"/api/organizations/{org_id}/categories/{cat1['id']}",
        json={"name": "Fresh Bakery"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Fresh Bakery"

    # Attempt update to collision with cat2 ("Dairy") -> 409
    col_resp = await api_client.patch(
        f"/api/organizations/{org_id}/categories/{cat1['id']}",
        json={"name": "dairy"},
        headers=headers,
    )
    assert col_resp.status_code == 409

    # 5. Archive category (First archive call)
    arch_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories/{cat1['id']}/archive",
        headers=headers,
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "archived"
    t1_archived_at = arch_resp.json()["archived_at"]
    assert t1_archived_at is not None

    # Idempotent re-archive -> 200 OK, preserves exact original archived_at
    rearch_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories/{cat1['id']}/archive",
        headers=headers,
    )
    assert rearch_resp.status_code == 200
    assert rearch_resp.json()["status"] == "archived"
    assert rearch_resp.json()["archived_at"] == t1_archived_at

    # Attempt update on archived category -> 409
    uparch_resp = await api_client.patch(
        f"/api/organizations/{org_id}/categories/{cat1['id']}",
        json={"name": "Should Fail"},
        headers=headers,
    )
    assert uparch_resp.status_code == 409

    # 6. Filter categories by status
    active_list = await api_client.get(
        f"/api/organizations/{org_id}/categories?status=active",
        headers=headers,
    )
    assert active_list.status_code == 200
    assert active_list.json()["total"] == 1
    assert active_list.json()["items"][0]["id"] == cat2["id"]

    archived_list = await api_client.get(
        f"/api/organizations/{org_id}/categories?status=archived",
        headers=headers,
    )
    assert archived_list.status_code == 200
    assert archived_list.json()["total"] == 1
    assert archived_list.json()["items"][0]["id"] == cat1["id"]


@pytest.mark.asyncio
async def test_archive_category_is_naturally_idempotent(
    api_client: AsyncClient,
) -> None:
    """Verify archive idempotency:
    1. create active category
    2. archive category
    3. capture archived_at as T1
    4. archive same category again
    5. assert second call succeeds with 200
    6. assert status == archived
    7. assert archived_at == T1
    """
    _, token = await _create_user(api_client, "owner_idempotent")
    org_id = await _create_org(api_client, token, "Idempotent Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create active category
    create_resp = await api_client.post(
        f"/api/organizations/{org_id}/categories",
        json={"name": "Dry Fruits"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "active"
    assert create_resp.json()["archived_at"] is None

    # 2. Archive category
    arch_resp1 = await api_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=headers,
    )
    assert arch_resp1.status_code == 200
    assert arch_resp1.json()["status"] == "archived"

    # 3. Capture archived_at as T1
    t1 = arch_resp1.json()["archived_at"]
    assert t1 is not None

    # 4. Archive same category again
    arch_resp2 = await api_client.post(
        f"/api/organizations/{org_id}/categories/{cat_id}/archive",
        headers=headers,
    )

    # 5. Assert second call succeeds with 200
    assert arch_resp2.status_code == 200

    # 6. Assert status == archived
    assert arch_resp2.json()["status"] == "archived"

    # 7. Assert archived_at == T1
    assert arch_resp2.json()["archived_at"] == t1


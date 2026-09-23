"""PostgreSQL integration tests for inventory balances and movements persistence (INV-001)."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.organizations.models import Organization
from app.modules.products.models import Product


async def _create_test_org(db_session: AsyncSession, name: str = "Inv Org") -> Organization:
    """Create an organization directly in db_session."""
    org = Organization(
        id=uuid.uuid4(),
        display_name=name,
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()
    return org


async def _create_test_product(
    db_session: AsyncSession, org_id: uuid.UUID, code: str
) -> Product:
    """Create a product directly in db_session."""
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code=code,
        name=f"Product {code}",
        base_unit="piece",
        default_price_minor=10000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()
    return prod


@pytest.mark.asyncio
async def test_inventory_tables_structure_in_postgres(db_session: AsyncSession) -> None:
    """Verify inventory_balances and inventory_movements tables exist with expected columns."""
    balances_cols = await db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'inventory_balances'
            ORDER BY ordinal_position;
            """
        )
    )
    cols = {r[0]: (r[1], r[2]) for r in balances_cols.fetchall()}
    assert "id" in cols
    assert "organization_id" in cols
    assert "product_id" in cols
    assert "on_hand_quantity" in cols
    assert "version" in cols
    assert "updated_at" in cols
    assert cols["on_hand_quantity"][1] == "NO"

    movements_cols = await db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'inventory_movements'
            ORDER BY ordinal_position;
            """
        )
    )
    m_cols = {r[0]: (r[1], r[2]) for r in movements_cols.fetchall()}
    assert "id" in m_cols
    assert "organization_id" in m_cols
    assert "product_id" in m_cols
    assert "movement_type" in m_cols
    assert "quantity_delta" in m_cols
    assert "source_type" in m_cols
    assert "source_id" in m_cols
    assert "reason" in m_cols
    assert "created_by_user_id" in m_cols
    assert "created_at" in m_cols
    assert m_cols["quantity_delta"][1] == "NO"


@pytest.mark.asyncio
async def test_inventory_constraints_in_pg_catalog(db_session: AsyncSession) -> None:
    """Verify check and unique constraints registered in PostgreSQL catalog."""
    # Check constraints on inventory_balances
    bal_ck = await db_session.execute(
        text(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'inventory_balances'::regclass AND contype = 'c';
            """
        )
    )
    bal_cks = {r[0] for r in bal_ck.fetchall()}
    assert any("quantity_non_negative" in c for c in bal_cks)

    # Unique constraints on inventory_balances
    bal_uq = await db_session.execute(
        text(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'inventory_balances'::regclass AND contype = 'u';
            """
        )
    )
    bal_uqs = {r[0] for r in bal_uq.fetchall()}
    assert any("product_id" in c for c in bal_uqs)

    # Check constraints on inventory_movements
    mov_ck = await db_session.execute(
        text(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'inventory_movements'::regclass AND contype = 'c';
            """
        )
    )
    mov_cks = {r[0] for r in mov_ck.fetchall()}
    assert any("quantity_non_zero" in c for c in mov_cks)
    assert any("movement_type" in c for c in mov_cks)


@pytest.mark.asyncio
async def test_inventory_balances_constraints_enforced(db_session: AsyncSession) -> None:
    """Verify check constraints and uniqueness on inventory_balances at insert time."""
    org = await _create_test_org(db_session, "Bal Constraint Org")
    prod = await _create_test_product(db_session, org.id, "BAL-P1")

    # 1. Negative quantity violates check constraint
    async with db_session.begin_nested():
        neg_balance = InventoryBalance(
            organization_id=org.id,
            product_id=prod.id,
            on_hand_quantity=-10,
        )
        db_session.add(neg_balance)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # 2. Valid balance insertion
    valid_balance = InventoryBalance(
        organization_id=org.id,
        product_id=prod.id,
        on_hand_quantity=25,
    )
    db_session.add(valid_balance)
    await db_session.flush()

    # 3. Duplicate product_id violates unique constraint
    async with db_session.begin_nested():
        dup_balance = InventoryBalance(
            organization_id=org.id,
            product_id=prod.id,
            on_hand_quantity=50,
        )
        db_session.add(dup_balance)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_inventory_movements_constraints_enforced(db_session: AsyncSession) -> None:
    """Verify check constraints on inventory_movements at insert time."""
    org = await _create_test_org(db_session, "Mov Constraint Org")
    prod = await _create_test_product(db_session, org.id, "MOV-P1")

    # 1. Zero quantity delta violates check constraint
    async with db_session.begin_nested():
        zero_movement = InventoryMovement(
            organization_id=org.id,
            product_id=prod.id,
            movement_type=MovementType.ADJUSTMENT.value,
            quantity_delta=0,
            source_type=MovementSourceType.ADJUSTMENT.value,
            reason="Zero adjustment test",
        )
        db_session.add(zero_movement)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # 2. Invalid movement_type violates check constraint
    async with db_session.begin_nested():
        invalid_type_movement = InventoryMovement(
            organization_id=org.id,
            product_id=prod.id,
            movement_type="invalid_type",
            quantity_delta=10,
            source_type="test",
        )
        db_session.add(invalid_type_movement)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_inventory_repository_and_tenant_isolation(db_session: AsyncSession) -> None:
    """Verify InventoryRepository methods and strict tenant isolation."""
    org_a = await _create_test_org(db_session, "Org A Inventory")
    prod_a = await _create_test_product(db_session, org_a.id, "PROD-A")

    org_b = await _create_test_org(db_session, "Org B Inventory")
    prod_b = await _create_test_product(db_session, org_b.id, "PROD-B")

    repo_a = InventoryRepository(db_session, org_a.id)
    repo_b = InventoryRepository(db_session, org_b.id)

    # Org A creates balance and movement
    bal_a = await repo_a.create_balance(
        InventoryBalance(
            organization_id=org_a.id,
            product_id=prod_a.id,
            on_hand_quantity=100,
            version=1,
        )
    )
    mov_a = await repo_a.create_movement(
        InventoryMovement(
            organization_id=org_a.id,
            product_id=prod_a.id,
            movement_type=MovementType.OPENING.value,
            quantity_delta=100,
            source_type=MovementSourceType.OPENING.value,
            reason="Opening stock for Org A",
        )
    )

    # Org B creates balance and movement
    bal_b = await repo_b.create_balance(
        InventoryBalance(
            organization_id=org_b.id,
            product_id=prod_b.id,
            on_hand_quantity=50,
            version=1,
        )
    )
    mov_b = await repo_b.create_movement(
        InventoryMovement(
            organization_id=org_b.id,
            product_id=prod_b.id,
            movement_type=MovementType.OPENING.value,
            quantity_delta=50,
            source_type=MovementSourceType.OPENING.value,
            reason="Opening stock for Org B",
        )
    )

    # Repository A queries
    fetched_bal_a = await repo_a.get_balance_by_product_id(prod_a.id)
    assert fetched_bal_a is not None
    assert fetched_bal_a.id == bal_a.id
    assert fetched_bal_a.on_hand_quantity == 100

    # Repo A cannot see Prod B's balance
    assert await repo_a.get_balance_by_product_id(prod_b.id) is None

    # Repo A list balances only returns Org A balance
    balances_a, total_a = await repo_a.list_balances()
    assert total_a == 1
    assert balances_a[0].id == bal_a.id

    # Repo A list movements only returns Org A movements
    movements_a, total_mov_a = await repo_a.list_movements()
    assert total_mov_a == 1
    assert movements_a[0].id == mov_a.id
    assert movements_a[0].reason == "Opening stock for Org A"

    # Repo B queries
    fetched_bal_b = await repo_b.get_balance_by_product_id(prod_b.id)
    assert fetched_bal_b is not None
    assert fetched_bal_b.id == bal_b.id
    assert fetched_bal_b.on_hand_quantity == 50

    # Repo B cannot see Prod A's balance
    assert await repo_b.get_balance_by_product_id(prod_a.id) is None

    # Locking read via get_balance_for_update
    locked_bal_a = await repo_a.get_balance_for_update(prod_a.id)
    assert locked_bal_a is not None
    assert locked_bal_a.id == bal_a.id

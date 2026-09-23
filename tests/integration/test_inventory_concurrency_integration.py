"""PostgreSQL integration tests for inventory transaction and concurrency controls (INV-003)."""

from __future__ import annotations

import asyncio
import uuid
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.errors import ValidationException
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.schemas import AdjustmentRequest, OpeningStockRequest
from app.modules.inventory.service import InventoryService
from app.modules.inventory.transaction import locked_inventory_scope
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.products.models import Product


async def _create_committed_fixture(
    db_engine: AsyncEngine,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create committed test organization and product for multi-connection concurrency."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        org_id = uuid.uuid4()
        prod_id = uuid.uuid4()

        org = Organization(
            id=org_id,
            display_name="Concurrency Test Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status="active",
        )
        session.add(org)
        await session.flush()

        prod = Product(
            id=prod_id,
            organization_id=org_id,
            code="CONCUR-SKU-01",
            name="Concurrent Item",
            base_unit="piece",
            default_price_minor=1000,
            currency_code="PKR",
            status="active",
        )
        session.add(prod)
        await session.flush()

        # Set initial opening stock = 100
        service = InventoryService(
            session=session,
            organization_id=org_id,
            actor_role=MemberRole.OWNER,
        )
        await service.record_opening_stock(
            OpeningStockRequest(product_id=prod_id, quantity=100, reason="Base stock")
        )
        await session.commit()

        return org_id, prod_id


async def _cleanup_committed_fixture(
    db_engine: AsyncEngine, org_id: uuid.UUID
) -> None:
    """Clean up test records."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            delete(InventoryMovement).where(InventoryMovement.organization_id == org_id)
        )
        await session.execute(
            delete(InventoryBalance).where(InventoryBalance.organization_id == org_id)
        )
        await session.execute(
            delete(Product).where(Product.organization_id == org_id)
        )
        await session.execute(
            delete(Organization).where(Organization.id == org_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_stock_adjustments_serialization(db_engine: AsyncEngine) -> None:
    """Verify concurrent adjustments serialize correctly under row locking.

    Scenario:
    - Base stock: 100 units
    - 5 concurrent workers adding 10 units (+50)
    - 5 concurrent workers deducting 5 units (-25)
    - Expected final stock: 100 + 50 - 25 = 125 units
    - Version increments by 10 (1 -> 11)
    - Exactly 11 total movements (1 opening + 10 adjustments)
    """
    org_id, prod_id = await _create_committed_fixture(db_engine)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    try:
        deltas = [+10, -5, +10, -5, +10, -5, +10, -5, +10, -5]

        async def worker(delta: int, worker_idx: int) -> None:
            async with session_factory() as session:
                service = InventoryService(
                    session=session,
                    organization_id=org_id,
                    actor_role=MemberRole.MANAGER,
                )
                await service.record_adjustment(
                    AdjustmentRequest(
                        product_id=prod_id,
                        quantity_delta=delta,
                        reason=f"Concurrent worker {worker_idx} adjustment",
                    )
                )
                await session.commit()

        tasks = [worker(delta, i) for i, delta in enumerate(deltas)]
        await asyncio.gather(*tasks)

        # Verify final state
        async with session_factory() as session:
            service = InventoryService(
                session=session,
                organization_id=org_id,
                actor_role=MemberRole.OWNER,
            )
            bal = await service.get_balance(prod_id)
            assert bal is not None
            assert bal.on_hand_quantity == 125
            assert bal.version == 11

            movements_resp = await service.list_movements(product_id=prod_id, limit=50)
            assert movements_resp.total == 11

    finally:
        await _cleanup_committed_fixture(db_engine, org_id)


@pytest.mark.asyncio
async def test_concurrent_depletion_never_allows_negative_balance(db_engine: AsyncEngine) -> None:
    """Verify concurrent attempts to deplete stock beyond available balance are strictly rejected.

    Scenario:
    - Initial stock: 10 units (create fresh fixture with 10 units)
    - 5 concurrent workers each trying to deduct 5 units (total requested deduction = 25)
    - Exactly 2 workers can succeed (10 - 5 - 5 = 0)
    - 3 workers MUST fail with ValidationException
    - Final balance MUST be exactly 0, never negative
    """
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    # Setup fixture with 10 units
    async with session_factory() as session:
        org = Organization(
            id=org_id,
            display_name="Depletion Test Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status="active",
        )
        session.add(org)
        await session.flush()

        prod = Product(
            id=prod_id,
            organization_id=org_id,
            code="DEPLETE-SKU-01",
            name="Depletion Item",
            base_unit="piece",
            default_price_minor=1000,
            currency_code="PKR",
            status="active",
        )
        session.add(prod)
        await session.flush()

        service = InventoryService(
            session=session,
            organization_id=org_id,
            actor_role=MemberRole.OWNER,
        )
        await service.record_opening_stock(
            OpeningStockRequest(product_id=prod_id, quantity=10, reason="Base stock 10")
        )
        await session.commit()

    try:
        success_count = 0
        failure_count = 0

        async def worker(worker_idx: int) -> bool:
            async with session_factory() as session:
                service = InventoryService(
                    session=session,
                    organization_id=org_id,
                    actor_role=MemberRole.MANAGER,
                )
                try:
                    await service.record_adjustment(
                        AdjustmentRequest(
                            product_id=prod_id,
                            quantity_delta=-5,
                            reason=f"Depletion worker {worker_idx}",
                        )
                    )
                    await session.commit()
                    return True
                except ValidationException:
                    await session.rollback()
                    return False

        results = await asyncio.gather(*[worker(i) for i in range(5)])

        success_count = sum(1 for r in results if r is True)
        failure_count = sum(1 for r in results if r is False)

        assert success_count == 2
        assert failure_count == 3

        # Verify final balance is strictly 0
        async with session_factory() as session:
            service = InventoryService(
                session=session,
                organization_id=org_id,
                actor_role=MemberRole.OWNER,
            )
            bal = await service.get_balance(prod_id)
            assert bal is not None
            assert bal.on_hand_quantity == 0
            assert bal.version == 3  # opening (1) + 2 successful adjustments = 3

    finally:
        await _cleanup_committed_fixture(db_engine, org_id)


@pytest.mark.asyncio
async def test_transaction_rollback_preserves_balance(db_session: AsyncSession) -> None:
    """Verify failed transaction rolls back both balance changes and movement records."""
    org = Organization(
        id=uuid.uuid4(),
        display_name="Rollback Test Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()

    prod = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code="ROLLBACK-SKU-01",
        name="Rollback Item",
        base_unit="piece",
        default_price_minor=1000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()

    service = InventoryService(
        session=db_session,
        organization_id=org.id,
        actor_role=MemberRole.OWNER,
    )
    await service.record_opening_stock(
        OpeningStockRequest(product_id=prod.id, quantity=50, reason="Base stock")
    )
    await db_session.flush()

    # Attempt an adjustment inside a nested savepoint that fails
    with pytest.raises(RuntimeError):
        async with db_session.begin_nested():
            await service.record_adjustment(
                AdjustmentRequest(
                    product_id=prod.id,
                    quantity_delta=10,
                    reason="Temporary adjustment",
                )
            )
            raise RuntimeError("Simulated mid-transaction failure")

    # Verify balance reverted to 50
    bal = await service.get_balance(prod.id)
    assert bal is not None
    assert bal.on_hand_quantity == 50
    assert bal.version == 1

    # Verify only opening movement exists
    movements_resp = await service.list_movements(product_id=prod.id)
    assert movements_resp.total == 1


@pytest.mark.asyncio
async def test_locked_inventory_scope_context_manager(db_session: AsyncSession) -> None:
    """Verify locked_inventory_scope retrieves balance with row lock and tenant isolation."""
    org = Organization(
        id=uuid.uuid4(),
        display_name="Locked Scope Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()

    prod = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code="SCOPE-SKU-01",
        name="Scope Item",
        base_unit="piece",
        default_price_minor=1000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()

    service = InventoryService(
        session=db_session,
        organization_id=org.id,
        actor_role=MemberRole.OWNER,
    )
    await service.record_opening_stock(
        OpeningStockRequest(product_id=prod.id, quantity=30, reason="Opening")
    )

    async with locked_inventory_scope(db_session, org.id, prod.id) as balance:
        assert balance is not None
        assert balance.on_hand_quantity == 30
        assert balance.product_id == prod.id

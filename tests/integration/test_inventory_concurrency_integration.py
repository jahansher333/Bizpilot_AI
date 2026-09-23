"""PostgreSQL integration tests for inventory transaction and concurrency controls (INV-003)."""

from __future__ import annotations

import asyncio
import uuid
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.errors import ConflictException, ValidationException
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


@pytest.mark.asyncio
async def test_concurrent_first_balance_creation_race_resolves_to_single_balance(
    db_engine: AsyncEngine,
) -> None:
    """Verify concurrent workers racing to create the first balance resolve to exactly one balance.

    Preconditions:
    - Organization exists and is committed.
    - Product exists and is committed.
    - NO inventory_balance row exists beforehand.

    Scenario:
    - 5 concurrent workers race to create opening stock on the same uninitialized product.
    - Workers are synchronized via asyncio.Event to hit the database concurrently.
    - Exactly 1 worker must succeed and commit.
    - 4 losing workers must fail with ConflictException and roll back.
    - Exactly 1 inventory_balance row survives with version = 1.
    - Winning worker's movement is recorded; losing workers leave ZERO orphan movements.
    - Final balance on_hand_quantity matches the winning movement quantity delta.
    - Zero negative stock and zero state corruption.
    """
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    # Precondition: Create committed org and product with NO inventory_balance
    async with session_factory() as session:
        org = Organization(
            id=org_id,
            display_name="First Balance Concurrency Org",
            currency_code="PKR",
            timezone="Asia/Karachi",
            status="active",
        )
        session.add(org)
        await session.flush()

        prod = Product(
            id=prod_id,
            organization_id=org_id,
            code="FIRST-BAL-01",
            name="First Balance Item",
            base_unit="piece",
            default_price_minor=1500,
            currency_code="PKR",
            status="active",
        )
        session.add(prod)
        await session.commit()

    try:
        # Precondition check: assert no balance exists beforehand
        async with session_factory() as session:
            initial_bal = await session.scalar(
                select(InventoryBalance).where(
                    InventoryBalance.organization_id == org_id,
                    InventoryBalance.product_id == prod_id,
                )
            )
            assert initial_bal is None, "Precondition violated: balance already exists"

        start_gate = asyncio.Event()

        async def worker(worker_idx: int) -> bool:
            async with session_factory() as session:
                service = InventoryService(
                    session=session,
                    organization_id=org_id,
                    actor_role=MemberRole.OWNER,
                )
                await start_gate.wait()
                try:
                    await service.record_opening_stock(
                        OpeningStockRequest(
                            product_id=prod_id,
                            quantity=100,
                            reason=f"Opening race worker {worker_idx}",
                        )
                    )
                    await session.commit()
                    return True
                except ConflictException:
                    await session.rollback()
                    return False

        # Spawn 5 concurrent racing workers
        tasks = [asyncio.create_task(worker(i)) for i in range(5)]
        # Yield control briefly so all workers reach start_gate.wait()
        await asyncio.sleep(0.05)
        # Release the gate simultaneously
        start_gate.set()
        results = await asyncio.gather(*tasks)

        successes = sum(1 for r in results if r is True)
        failures = sum(1 for r in results if r is False)

        # 1. Exactly ONE worker successfully creates the balance; 4 fail with ConflictException
        assert successes == 1, f"Expected exactly 1 winner, got {successes}"
        assert failures == 4, f"Expected exactly 4 losers, got {failures}"

        # 2. Verify database state
        async with session_factory() as session:
            # 3. No duplicate inventory_balance rows are created (exactly 1 exists)
            balance_rows = (
                await session.scalars(
                    select(InventoryBalance).where(
                        InventoryBalance.organization_id == org_id,
                        InventoryBalance.product_id == prod_id,
                    )
                )
            ).all()
            assert len(balance_rows) == 1
            surviving_balance = balance_rows[0]
            assert surviving_balance.on_hand_quantity == 100
            assert surviving_balance.version == 1

            # 4. Winning worker's movement is recorded; losing workers leave ZERO orphan movements
            movement_rows = (
                await session.scalars(
                    select(InventoryMovement).where(
                        InventoryMovement.organization_id == org_id,
                        InventoryMovement.product_id == prod_id,
                    )
                )
            ).all()
            assert len(movement_rows) == 1, (
                f"Expected exactly 1 movement row (winner only), got {len(movement_rows)}"
            )
            assert movement_rows[0].movement_type == MovementType.OPENING.value
            assert movement_rows[0].quantity_delta == 100

            # 5. Final balance matches winning movement
            assert surviving_balance.on_hand_quantity == sum(
                m.quantity_delta for m in movement_rows
            )
            assert surviving_balance.on_hand_quantity >= 0

    finally:
        await _cleanup_committed_fixture(db_engine, org_id)

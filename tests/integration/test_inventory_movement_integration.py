"""PostgreSQL integration tests for InventoryService movement and trace persistence (INV-002)."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.schemas import (
    AdjustmentRequest,
    CorrectionRequest,
    OpeningStockRequest,
    VoidReversalRequest,
)
from app.modules.inventory.service import InventoryService
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.products.models import Product
from app.modules.trace.enums import TraceAction
from app.modules.trace.models import InternalTraceEvent


async def _create_test_org(db_session: AsyncSession, name: str = "Movement Org") -> Organization:
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
    prod = Product(
        id=uuid.uuid4(),
        organization_id=org_id,
        code=code,
        name=f"Product {code}",
        base_unit="piece",
        default_price_minor=5000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()
    return prod


@pytest.mark.asyncio
async def test_opening_stock_lifecycle_in_postgres(db_session: AsyncSession) -> None:
    """Verify opening stock persists balance and movement, and rejects duplicate opening."""
    org = await _create_test_org(db_session, "Opening Stock Org")
    prod = await _create_test_product(db_session, org.id, "PROD-OPEN-01")

    service = InventoryService(
        session=db_session,
        organization_id=org.id,
        actor_role=MemberRole.OWNER,
    )

    req = OpeningStockRequest(product_id=prod.id, quantity=100, reason="Initial stock entry")
    bal_resp, mov_resp = await service.record_opening_stock(req)

    assert bal_resp.on_hand_quantity == 100
    assert bal_resp.version == 1
    assert mov_resp.quantity_delta == 100
    assert mov_resp.movement_type == MovementType.OPENING.value

    # Verify directly from database
    bal_row = await db_session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.organization_id == org.id,
            InventoryBalance.product_id == prod.id,
        )
    )
    assert bal_row is not None
    assert bal_row.on_hand_quantity == 100

    mov_rows = (
        await db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.organization_id == org.id,
                InventoryMovement.product_id == prod.id,
            )
        )
    ).all()
    assert len(mov_rows) == 1
    assert mov_rows[0].movement_type == "opening"
    assert mov_rows[0].quantity_delta == 100

    # Duplicate opening stock must raise ConflictException
    with pytest.raises(ConflictException, match="already been recorded"):
        await service.record_opening_stock(req)


@pytest.mark.asyncio
async def test_adjustments_and_negative_stock_rejection(db_session: AsyncSession) -> None:
    """Verify sequential adjustments update balance and version, rejecting negative result."""
    org = await _create_test_org(db_session, "Adj Org")
    prod = await _create_test_product(db_session, org.id, "PROD-ADJ-01")

    service = InventoryService(
        session=db_session,
        organization_id=org.id,
        actor_role=MemberRole.MANAGER,
    )

    # Initial opening stock: 50
    await service.record_opening_stock(
        OpeningStockRequest(product_id=prod.id, quantity=50, reason="Starting stock")
    )

    # Positive adjustment: +20
    bal1, mov1 = await service.record_adjustment(
        AdjustmentRequest(product_id=prod.id, quantity_delta=20, reason="Found in storeroom")
    )
    assert bal1.on_hand_quantity == 70
    assert bal1.version == 2
    assert mov1.quantity_delta == 20

    # Negative adjustment: -30
    bal2, mov2 = await service.record_adjustment(
        AdjustmentRequest(product_id=prod.id, quantity_delta=-30, reason="Breakage writeoff")
    )
    assert bal2.on_hand_quantity == 40
    assert bal2.version == 3
    assert mov2.quantity_delta == -30

    # Excessive negative adjustment: -50 (only 40 available) -> must fail
    with pytest.raises(ValidationException, match="Insufficient stock on hand"):
        await service.record_adjustment(
            AdjustmentRequest(product_id=prod.id, quantity_delta=-50, reason="Oversold")
        )

    # Balance remains 40 in DB
    current_bal = await service.get_balance(prod.id)
    assert current_bal is not None
    assert current_bal.on_hand_quantity == 40
    assert current_bal.version == 3


@pytest.mark.asyncio
async def test_correction_and_void_reversal_with_trace_persistence(db_session: AsyncSession) -> None:
    """Verify correction and void reversal mutate stock and persist internal trace events in DB."""
    org = await _create_test_org(db_session, "Trace Org")
    prod = await _create_test_product(db_session, org.id, "PROD-TRACE-01")

    service = InventoryService(
        session=db_session,
        organization_id=org.id,
        actor_role=MemberRole.OWNER,
    )

    # Start with 25 units
    await service.record_opening_stock(
        OpeningStockRequest(product_id=prod.id, quantity=25, reason="Batch initial")
    )

    # Record correction: -5
    bal_corr, mov_corr = await service.record_correction(
        CorrectionRequest(product_id=prod.id, quantity_delta=-5, reason="Count variance correction")
    )
    assert bal_corr.on_hand_quantity == 20
    assert mov_corr.movement_type == MovementType.CORRECTION.value

    # Verify trace event for correction
    corr_trace = await db_session.scalar(
        select(InternalTraceEvent).where(
            InternalTraceEvent.organization_id == org.id,
            InternalTraceEvent.action == TraceAction.FINANCE_RECORD_CORRECTED.value,
            InternalTraceEvent.target_id == mov_corr.id,
        )
    )
    assert corr_trace is not None
    assert corr_trace.outcome == "success"
    assert corr_trace.event_metadata["quantity_delta"] == -5
    assert corr_trace.event_metadata["previous_quantity"] == 25
    assert corr_trace.event_metadata["new_quantity"] == 20

    # Record void reversal: +10
    bal_void, mov_void = await service.record_void_reversal(
        VoidReversalRequest(
            product_id=prod.id,
            quantity_delta=10,
            source_id=mov_corr.id,
            reason="Reversed previous correction",
        )
    )
    assert bal_void.on_hand_quantity == 30
    assert mov_void.movement_type == MovementType.VOID_REVERSAL.value

    # Verify trace event for void reversal
    void_trace = await db_session.scalar(
        select(InternalTraceEvent).where(
            InternalTraceEvent.organization_id == org.id,
            InternalTraceEvent.action == TraceAction.FINANCE_RECORD_VOIDED.value,
            InternalTraceEvent.target_id == mov_void.id,
        )
    )
    assert void_trace is not None
    assert void_trace.outcome == "success"
    assert void_trace.event_metadata["quantity_delta"] == 10
    assert void_trace.event_metadata["previous_quantity"] == 20
    assert void_trace.event_metadata["new_quantity"] == 30


@pytest.mark.asyncio
async def test_tenant_isolation_in_service(db_session: AsyncSession) -> None:
    """Verify tenant isolation prevents modifying or reading another organization's inventory."""
    org1 = await _create_test_org(db_session, "Org One")
    org2 = await _create_test_org(db_session, "Org Two")

    prod1 = await _create_test_product(db_session, org1.id, "PROD-ORG1")

    # Service bound to org2 cannot access prod1
    service2 = InventoryService(
        session=db_session,
        organization_id=org2.id,
        actor_role=MemberRole.OWNER,
    )

    with pytest.raises(NotFoundException):
        await service2.record_opening_stock(
            OpeningStockRequest(product_id=prod1.id, quantity=100)
        )

    with pytest.raises(NotFoundException):
        await service2.record_adjustment(
            AdjustmentRequest(product_id=prod1.id, quantity_delta=5, reason="Adjustment")
        )

    assert await service2.get_balance(prod1.id) is None

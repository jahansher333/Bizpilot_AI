"""Unit tests for InventoryService domain logic (INV-002)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.errors import (
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
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
from app.modules.products.enums import ProductStatus
from app.modules.products.models import Product
from app.modules.trace.enums import TraceAction, TraceOutcome


def _create_mock_product(
    product_id: uuid.UUID,
    org_id: uuid.UUID,
    status: ProductStatus = ProductStatus.ACTIVE,
) -> Product:
    return Product(
        id=product_id,
        organization_id=org_id,
        code="SKU-100",
        name="Test Product",
        base_unit="unit",
        default_price_minor=1000,
        currency_code="PKR",
        status=status.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_schema_validations() -> None:
    """Verify pydantic validations on request schemas."""
    pid = uuid.uuid4()

    # OpeningStock: quantity must be > 0
    with pytest.raises(ValidationError):
        OpeningStockRequest(product_id=pid, quantity=0)
    with pytest.raises(ValidationError):
        OpeningStockRequest(product_id=pid, quantity=-5)

    valid_opening = OpeningStockRequest(product_id=pid, quantity=10, reason="Initial stock")
    assert valid_opening.quantity == 10

    # AdjustmentRequest: delta != 0, reason min 3 chars
    with pytest.raises(ValidationError):
        AdjustmentRequest(product_id=pid, quantity_delta=0, reason="Adjustment")
    with pytest.raises(ValidationError):
        AdjustmentRequest(product_id=pid, quantity_delta=5, reason="ok")

    valid_adj = AdjustmentRequest(product_id=pid, quantity_delta=-2, reason="Shrinkage")
    assert valid_adj.quantity_delta == -2

    # CorrectionRequest: delta != 0, reason min 3 chars
    with pytest.raises(ValidationError):
        CorrectionRequest(product_id=pid, quantity_delta=0, reason="Correction")
    with pytest.raises(ValidationError):
        CorrectionRequest(product_id=pid, quantity_delta=5, reason="ab")

    valid_corr = CorrectionRequest(product_id=pid, quantity_delta=3, reason="Audit found 3 more")
    assert valid_corr.quantity_delta == 3

    # VoidReversalRequest: delta != 0
    with pytest.raises(ValidationError):
        VoidReversalRequest(product_id=pid, quantity_delta=0)

    valid_rev = VoidReversalRequest(product_id=pid, quantity_delta=-1)
    assert valid_rev.quantity_delta == -1


@pytest.mark.asyncio
async def test_record_opening_stock_success() -> None:
    """Verify successful recording of opening stock creates balance and movement."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()
    trace_service = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)
    repo.has_opening_movement.return_value = False
    repo.get_balance_for_update.return_value = None

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.OWNER,
        repository=repo,
        product_repository=prod_repo,
        trace_service=trace_service,
    )

    req = OpeningStockRequest(product_id=product_id, quantity=100, reason="Initial warehouse stock")
    balance_resp, movement_resp = await service.record_opening_stock(req)

    assert balance_resp.product_id == product_id
    assert balance_resp.on_hand_quantity == 100
    assert balance_resp.version == 1

    assert movement_resp.product_id == product_id
    assert movement_resp.movement_type == MovementType.OPENING.value
    assert movement_resp.quantity_delta == 100
    assert movement_resp.source_type == MovementSourceType.OPENING.value
    assert movement_resp.reason == "Initial warehouse stock"

    repo.create_balance.assert_awaited_once()
    repo.create_movement.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_opening_stock_duplicate_rejected() -> None:
    """Verify duplicate opening stock request raises ConflictException."""
    org_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()
    trace_service = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)
    repo.has_opening_movement.return_value = True

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_role=MemberRole.MANAGER,
        repository=repo,
        product_repository=prod_repo,
        trace_service=trace_service,
    )

    req = OpeningStockRequest(product_id=product_id, quantity=50)
    with pytest.raises(ConflictException, match="already been recorded"):
        await service.record_opening_stock(req)


@pytest.mark.asyncio
async def test_record_opening_stock_archived_product_rejected() -> None:
    """Verify stock changes on archived product are rejected."""
    org_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(
        product_id, org_id, status=ProductStatus.ARCHIVED
    )

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_role=MemberRole.OWNER,
        repository=repo,
        product_repository=prod_repo,
    )

    req = OpeningStockRequest(product_id=product_id, quantity=50)
    with pytest.raises(ConflictException, match="archived"):
        await service.record_opening_stock(req)


@pytest.mark.asyncio
async def test_staff_cannot_adjust_stock() -> None:
    """Verify Staff role cannot record adjustments."""
    org_id = uuid.uuid4()
    product_id = uuid.uuid4()

    service = InventoryService(
        session=AsyncMock(),
        organization_id=org_id,
        actor_role=MemberRole.STAFF,
        repository=AsyncMock(),
        product_repository=AsyncMock(),
    )

    req = AdjustmentRequest(product_id=product_id, quantity_delta=5, reason="Found stock")
    with pytest.raises(AuthorizationException):
        await service.record_adjustment(req)


@pytest.mark.asyncio
async def test_record_adjustment_positive_and_negative() -> None:
    """Verify positive and negative adjustments update balance and increment version."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)

    # Existing balance has 20 units, version 1
    existing_balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=product_id,
        on_hand_quantity=20,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    repo.get_balance_for_update.return_value = existing_balance

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.MANAGER,
        repository=repo,
        product_repository=prod_repo,
    )

    # Deduct 5 units
    req = AdjustmentRequest(product_id=product_id, quantity_delta=-5, reason="Damaged items written off")
    bal, mov = await service.record_adjustment(req)

    assert bal.on_hand_quantity == 15
    assert bal.version == 2
    assert mov.quantity_delta == -5
    assert mov.movement_type == MovementType.ADJUSTMENT.value
    assert mov.reason == "Damaged items written off"


@pytest.mark.asyncio
async def test_record_adjustment_negative_stock_rejected() -> None:
    """Verify adjustment that would result in negative on_hand_quantity is rejected."""
    org_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)

    existing_balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=product_id,
        on_hand_quantity=5,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    repo.get_balance_for_update.return_value = existing_balance

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_role=MemberRole.OWNER,
        repository=repo,
        product_repository=prod_repo,
    )

    # Attempt to deduct 10 units when only 5 exist
    req = AdjustmentRequest(product_id=product_id, quantity_delta=-10, reason="Stock check deficit")
    with pytest.raises(ValidationException, match="Insufficient stock on hand"):
        await service.record_adjustment(req)


@pytest.mark.asyncio
async def test_record_correction_emits_trace_event() -> None:
    """Verify correction updates balance, movement, and calls InternalTraceService."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()
    trace_service = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)

    existing_balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=product_id,
        on_hand_quantity=10,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    repo.get_balance_for_update.return_value = existing_balance

    service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.OWNER,
        repository=repo,
        product_repository=prod_repo,
        trace_service=trace_service,
    )

    req = CorrectionRequest(product_id=product_id, quantity_delta=2, reason="Cycle count correction")
    bal, mov = await service.record_correction(req)

    assert bal.on_hand_quantity == 12
    assert mov.movement_type == MovementType.CORRECTION.value
    assert mov.quantity_delta == 2

    trace_service.record_event.assert_awaited_once_with(
        action=TraceAction.FINANCE_RECORD_CORRECTED,
        outcome=TraceOutcome.SUCCESS,
        actor_user_id=user_id,
        target_type="inventory_movement",
        target_id=mov.id,
        metadata={
            "product_id": str(product_id),
            "quantity_delta": 2,
            "previous_quantity": 10,
            "new_quantity": 12,
            "reason": "Cycle count correction",
        },
    )


@pytest.mark.asyncio
async def test_record_void_reversal_permissions_and_trace() -> None:
    """Verify Manager/Staff cannot void, but Owner can and emits trace."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session = AsyncMock()
    repo = AsyncMock()
    prod_repo = AsyncMock()
    trace_service = AsyncMock()

    prod_repo.get_by_id.return_value = _create_mock_product(product_id, org_id)

    # Manager should be forbidden
    manager_service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.MANAGER,
        repository=repo,
        product_repository=prod_repo,
    )
    req = VoidReversalRequest(product_id=product_id, quantity_delta=5, reason="Reversal of mistaken writeoff")
    with pytest.raises(AuthorizationException, match="Only organization owner"):
        await manager_service.record_void_reversal(req)

    # Owner should succeed
    existing_balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org_id,
        product_id=product_id,
        on_hand_quantity=10,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    repo.get_balance_for_update.return_value = existing_balance

    owner_service = InventoryService(
        session=session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.OWNER,
        repository=repo,
        product_repository=prod_repo,
        trace_service=trace_service,
    )

    bal, mov = await owner_service.record_void_reversal(req)
    assert bal.on_hand_quantity == 15
    assert mov.movement_type == MovementType.VOID_REVERSAL.value

    trace_service.record_event.assert_awaited_once_with(
        action=TraceAction.FINANCE_RECORD_VOIDED,
        outcome=TraceOutcome.SUCCESS,
        actor_user_id=user_id,
        target_type="inventory_movement",
        target_id=mov.id,
        metadata={
            "product_id": str(product_id),
            "quantity_delta": 5,
            "previous_quantity": 10,
            "new_quantity": 15,
            "source_id": None,
            "reason": "Reversal of mistaken writeoff",
        },
    )

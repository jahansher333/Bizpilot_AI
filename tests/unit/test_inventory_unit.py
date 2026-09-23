"""Unit tests for inventory models, schemas, and enums (INV-001)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.db.repositories import TenantScopedModel
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.inventory.schemas import (
    InventoryBalanceListResponse,
    InventoryBalanceResponse,
    InventoryMovementListResponse,
    InventoryMovementResponse,
)


def test_inventory_balance_model_satisfies_tenant_scoped_protocol() -> None:
    """InventoryBalance must satisfy TenantScopedModel protocol."""
    balance = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        on_hand_quantity=10,
        version=1,
    )
    assert isinstance(balance, TenantScopedModel)
    assert balance.id is not None
    assert balance.organization_id is not None
    assert balance.on_hand_quantity == 10
    assert balance.version == 1


def test_inventory_movement_model_satisfies_tenant_scoped_protocol() -> None:
    """InventoryMovement must satisfy TenantScopedModel protocol."""
    movement = InventoryMovement(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        movement_type=MovementType.OPENING.value,
        quantity_delta=50,
        source_type=MovementSourceType.OPENING.value,
        reason="Initial stock",
    )
    assert isinstance(movement, TenantScopedModel)
    assert movement.id is not None
    assert movement.organization_id is not None
    assert movement.quantity_delta == 50
    assert movement.movement_type == "opening"


def test_movement_type_enums() -> None:
    """Verify supported movement types."""
    assert MovementType.OPENING.value == "opening"
    assert MovementType.SALE.value == "sale"
    assert MovementType.ADJUSTMENT.value == "adjustment"
    assert MovementType.CORRECTION.value == "correction"
    assert MovementType.VOID_REVERSAL.value == "void_reversal"


def test_movement_source_type_enums() -> None:
    """Verify supported movement source types."""
    assert MovementSourceType.OPENING.value == "opening"
    assert MovementSourceType.ORDER.value == "order"
    assert MovementSourceType.ADJUSTMENT.value == "adjustment"
    assert MovementSourceType.CORRECTION.value == "correction"
    assert MovementSourceType.VOID_REVERSAL.value == "void_reversal"


def test_inventory_balance_response_schema() -> None:
    """Verify valid balance response serialization."""
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "product_id": uuid.uuid4(),
        "on_hand_quantity": 100,
        "version": 1,
        "updated_at": now,
    }
    resp = InventoryBalanceResponse.model_validate(data)
    assert resp.on_hand_quantity == 100
    assert resp.version == 1


def test_inventory_balance_response_extra_fields_forbidden() -> None:
    """Extra fields must be rejected in balance schema."""
    with pytest.raises(ValidationError):
        InventoryBalanceResponse.model_validate(
            {
                "id": uuid.uuid4(),
                "organization_id": uuid.uuid4(),
                "product_id": uuid.uuid4(),
                "on_hand_quantity": 100,
                "version": 1,
                "updated_at": datetime.now(timezone.utc),
                "unapproved_field": "injected",
            }
        )


def test_inventory_movement_response_schema() -> None:
    """Verify valid movement response serialization."""
    now = datetime.now(timezone.utc)
    data = {
        "id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "product_id": uuid.uuid4(),
        "movement_type": "adjustment",
        "quantity_delta": -5,
        "source_type": "adjustment",
        "source_id": uuid.uuid4(),
        "reason": "Damaged goods in storage",
        "created_by_user_id": uuid.uuid4(),
        "created_at": now,
    }
    resp = InventoryMovementResponse.model_validate(data)
    assert resp.movement_type == MovementType.ADJUSTMENT
    assert resp.quantity_delta == -5
    assert resp.reason == "Damaged goods in storage"


def test_inventory_movement_response_extra_fields_forbidden() -> None:
    """Extra fields must be rejected in movement schema."""
    with pytest.raises(ValidationError):
        InventoryMovementResponse.model_validate(
            {
                "id": uuid.uuid4(),
                "organization_id": uuid.uuid4(),
                "product_id": uuid.uuid4(),
                "movement_type": "sale",
                "quantity_delta": -2,
                "source_type": "order",
                "source_id": None,
                "reason": None,
                "created_by_user_id": None,
                "created_at": datetime.now(timezone.utc),
                "extra": "forbidden",
            }
        )

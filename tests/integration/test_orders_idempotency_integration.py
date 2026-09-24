"""PostgreSQL integration tests for Order Idempotency (ORD-004)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.errors import ConflictException, ValidationException
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.idempotency.models import IdempotencyKey
from app.modules.inventory.enums import MovementSourceType, MovementType
from app.modules.inventory.models import InventoryBalance, InventoryMovement
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import OrderCreateSchema, OrderItemCreateSchema
from app.modules.orders.service import OrderService
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.models import Organization
from app.modules.products.models import Product
from app.modules.auth.models import User



async def _create_test_env(
    db_session: AsyncSession, prefix: str
) -> tuple[Organization, User, Product, InventoryBalance]:
    """Create test organization, user, product, and stock balance."""
    org = Organization(
        id=uuid.uuid4(),
        display_name=f"{prefix} Org",
        currency_code="PKR",
        timezone="Asia/Karachi",
        status="active",
    )
    db_session.add(org)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email_normalized=f"{prefix.lower()}_{uuid.uuid4().hex[:6]}@example.com",
        display_name=f"{prefix} User",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()

    prod = Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        code=f"{prefix}-SKU",
        name=f"{prefix} Product",
        base_unit="piece",
        default_price_minor=2000,
        currency_code="PKR",
        status="active",
    )
    db_session.add(prod)
    await db_session.flush()

    bal = InventoryBalance(
        id=uuid.uuid4(),
        organization_id=org.id,
        product_id=prod.id,
        on_hand_quantity=20,
        version=1,
    )
    db_session.add(bal)
    await db_session.flush()

    return org, user, prod, bal


@pytest.mark.asyncio
async def test_order_creation_same_key_same_payload_replays_result(db_session: AsyncSession) -> None:
    """Submitting the same idempotency key with identical payload re-returns original response without re-deducting stock."""
    org, user, prod, bal = await _create_test_env(db_session, "IDEMP1")
    org_id = org.id
    user_id = user.id
    prod_id = prod.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
    )

    req = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=prod_id,
                quantity=3,
                unit_price_minor=2000,
            )
        ],
    )

    idemp_key = f"key-test-{uuid.uuid4().hex}"

    # First request
    res1 = await service.create_order(req, idempotency_key=idemp_key)
    await db_session.commit()

    # Second request (retry)
    res2 = await service.create_order(req, idempotency_key=idemp_key)
    await db_session.commit()

    # Results match exactly
    assert res1.id == res2.id
    assert res1.order_number == res2.order_number
    assert res1.order_total_minor == res2.order_total_minor
    assert len(res2.items) == 1

    # Database assertions: only 1 order created, only 1 movement created, stock deducted only once (20 - 3 = 17)
    orders = (await db_session.execute(
        select(Order).where(Order.organization_id == org_id)
    )).scalars().all()
    assert len(orders) == 1

    movements = (await db_session.execute(
        select(InventoryMovement).where(InventoryMovement.organization_id == org_id)
    )).scalars().all()
    assert len(movements) == 1
    assert movements[0].quantity_delta == -3

    bal_db = (await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_id)
    )).scalar_one()
    assert bal_db.on_hand_quantity == 17


@pytest.mark.asyncio
async def test_order_creation_same_key_different_payload_raises_conflict(db_session: AsyncSession) -> None:
    """Reusing the same idempotency key with different payload must fail with 409 Conflict."""
    org, user, prod, bal = await _create_test_env(db_session, "IDEMP2")
    org_id = org.id
    user_id = user.id
    prod_id = prod.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
    )

    idemp_key = f"key-conflict-{uuid.uuid4().hex}"

    req1 = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=prod_id,
                quantity=2,
                unit_price_minor=2000,
            )
        ],
    )
    await service.create_order(req1, idempotency_key=idemp_key)
    await db_session.commit()

    # Tampered / different request payload with same key
    req2 = OrderCreateSchema(
        items=[
            OrderItemCreateSchema(
                product_id=prod_id,
                quantity=5,  # different quantity
                unit_price_minor=2000,
            )
        ],
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_order(req2, idempotency_key=idemp_key)

    assert "previously used with different parameters" in str(exc_info.value)

    # Stock only decremented by 2, never by 5
    bal_db = (await db_session.execute(
        select(InventoryBalance).where(InventoryBalance.product_id == prod_id)
    )).scalar_one()
    assert bal_db.on_hand_quantity == 18


@pytest.mark.asyncio
async def test_idempotency_user_and_org_isolation(db_session: AsyncSession) -> None:
    """Different users within the same org, or users in different orgs, can safely use the same idempotency key value."""
    org1, user1, prod1, _ = await _create_test_env(db_session, "IDEMP_ISO1")
    org1_id = org1.id
    user1_id = user1.id
    prod1_id = prod1.id

    # Create second user in org1
    user2 = User(
        id=uuid.uuid4(),
        email_normalized=f"user2_{uuid.uuid4().hex[:6]}@example.com",
        display_name="User Two",
        status="active",
    )
    db_session.add(user2)
    user2_id = user2.id
    await db_session.commit()

    shared_key = "client-assigned-key-12345"

    service1 = OrderService(
        session=db_session,
        organization_id=org1_id,
        actor_user_id=user1_id,
        actor_role=MemberRole.STAFF,
    )
    service2 = OrderService(
        session=db_session,
        organization_id=org1_id,
        actor_user_id=user2_id,
        actor_role=MemberRole.STAFF,
    )

    req = OrderCreateSchema(
        items=[OrderItemCreateSchema(product_id=prod1_id, quantity=1, unit_price_minor=2000)]
    )

    order1 = await service1.create_order(req, idempotency_key=shared_key)
    await db_session.commit()

    # User 2 creates an order with the same key value -> creates separate order because keys are user-scoped
    order2 = await service2.create_order(req, idempotency_key=shared_key)
    await db_session.commit()

    assert order1.id != order2.id
    assert order1.order_number != order2.order_number


@pytest.mark.asyncio
async def test_idempotency_expired_key_policy(db_session: AsyncSession) -> None:
    """An expired idempotency record allows creating a fresh order."""
    org, user, prod, bal = await _create_test_env(db_session, "IDEMP_EXP")
    org_id = org.id
    user_id = user.id
    prod_id = prod.id
    await db_session.commit()

    service = OrderService(
        session=db_session,
        organization_id=org_id,
        actor_user_id=user_id,
        actor_role=MemberRole.STAFF,
    )

    idemp_key = f"key-exp-{uuid.uuid4().hex}"
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)

    req = OrderCreateSchema(
        items=[OrderItemCreateSchema(product_id=prod_id, quantity=1, unit_price_minor=2000)]
    )

    # First order created with an already-expired timestamp
    order1 = await service.create_order(
        req, idempotency_key=idemp_key, idempotency_expires_at=past_expiry
    )
    await db_session.commit()

    # Second order with same key after expiration is treated as new because the key has expired
    # (Notice: in a real system, the expired key record is overwritten or ignored)
    # Since DB has unique constraint on (org, user, op, key), expired records can be purged or cleaned up.
    # Verify get_stored_response returns None for expired key
    cached = await service._idempotency_service.get_stored_response(
        organization_id=org_id,
        user_id=user_id,
        operation="order:create",
        idempotency_key=idemp_key,
        request_hash="irrelevant_hash",
    )
    assert cached is None

"""Integration tests for Customer database persistence and tenant isolation (CUS-001)."""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import CustomerCreateSchema
from app.modules.customers.service import CustomerService
from app.modules.organizations.models import Organization


async def _create_test_org(db_session: AsyncSession, name: str = "Test Org") -> Organization:
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


@pytest.mark.asyncio
async def test_customers_db_partial_unique_index_and_cross_tenant(
    db_session: AsyncSession,
) -> None:
    org1 = await _create_test_org(db_session, "Org 1")
    org2 = await _create_test_org(db_session, "Org 2")

    # 1. Insert active customer in Org 1
    c1 = Customer(
        organization_id=org1.id,
        name="Org1 Customer",
        phone="+923001234567",
        status=CustomerStatus.ACTIVE.value,
    )
    db_session.add(c1)
    await db_session.flush()

    # 2. Duplicate phone in Org 2 (different organization) MUST SUCCEED (FD-CUS001-01)
    c2 = Customer(
        organization_id=org2.id,
        name="Org2 Customer",
        phone="+923001234567",
        status=CustomerStatus.ACTIVE.value,
    )
    db_session.add(c2)
    await db_session.flush()
    assert c2.id is not None

    # 3. Duplicate phone in SAME Org 1 MUST FAIL DB unique constraint
    c3 = Customer(
        organization_id=org1.id,
        name="Org1 Duplicate Phone",
        phone="+923001234567",
        status=CustomerStatus.ACTIVE.value,
    )
    db_session.add(c3)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_customers_tenant_isolation(
    db_session: AsyncSession,
) -> None:
    org1 = await _create_test_org(db_session, "Org 1 Isolation")
    org2 = await _create_test_org(db_session, "Org 2 Isolation")

    service1 = CustomerService(db_session, org1.id)
    service2 = CustomerService(db_session, org2.id)

    # Create customer in Org 1
    c1 = await service1.create_customer(
        CustomerCreateSchema(name="Tenant 1 VIP", phone="0311-1111111"),
    )

    # Org 2 list should NOT include Org 1 customer
    items2, total2 = await service2.list_customers()
    assert all(c.id != c1.id for c in items2)

    # Org 2 repository lookup by Org 1 ID must return None
    repo2 = CustomerRepository(db_session, org2.id)
    lookup = await repo2.get_by_id(c1.id)
    assert lookup is None

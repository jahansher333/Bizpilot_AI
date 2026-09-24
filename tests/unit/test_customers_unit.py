"""Unit tests for Customer schemas and service logic (CUS-001)."""

import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.modules.customers.enums import CustomerStatus
from app.modules.customers.schemas import (
    CustomerCreateSchema,
    CustomerUpdateSchema,
    normalize_phone,
)
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


def test_phone_normalization() -> None:
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("   ") is None
    assert normalize_phone("0300 1234567") == "03001234567"
    assert normalize_phone("0300-123-4567") == "03001234567"
    assert normalize_phone("+92 (300) 123-4567") == "03001234567"
    assert normalize_phone(" +92 300.123.4567 ") == "03001234567"
    assert normalize_phone("0092 300 1234567") == "03001234567"


def test_customer_create_schema_validations() -> None:
    valid = CustomerCreateSchema(
        name="Tariq Ali",
        phone="0300-1234567",
        email="tariq@example.com",
        notes="Wholesale buyer",
    )
    assert valid.name == "Tariq Ali"
    assert valid.phone == "03001234567"
    assert valid.email == "tariq@example.com"

    with pytest.raises(ValidationError):
        CustomerCreateSchema(name="   ")

    c_no_phone = CustomerCreateSchema(name="Walk-in Customer", phone="  ")
    assert c_no_phone.phone is None


def test_customer_update_schema_validations() -> None:
    update = CustomerUpdateSchema(
        name="Tariq Ahmed",
        phone="+92 300 9876543",
    )
    assert update.name == "Tariq Ahmed"
    assert update.phone == "03009876543"

    with pytest.raises(ValidationError):
        CustomerUpdateSchema(name="  ")


@pytest.mark.asyncio
async def test_customer_service_crud_and_uniqueness(db_session: AsyncSession) -> None:
    org = await _create_test_org(db_session, "Customer Org")
    org_id = org.id
    service = CustomerService(db_session, org_id)

    # 1. Create customer A
    cust_a = await service.create_customer(
        CustomerCreateSchema(
            name="Ahmed Khan",
            phone="0300-1111111",
            email="ahmed@example.com",
            notes="Retail customer",
        ),
    )
    assert cust_a.id is not None
    assert cust_a.name == "Ahmed Khan"
    assert cust_a.phone == "03001111111"
    assert cust_a.status == CustomerStatus.ACTIVE.value

    # 2. Duplicate names allowed in same organization (FD-CUS001-01)
    cust_dup_name = await service.create_customer(
        CustomerCreateSchema(
            name="Ahmed Khan",
            phone="0300-2222222",
        ),
    )
    assert cust_dup_name.id != cust_a.id
    assert cust_dup_name.name == "Ahmed Khan"

    # 3. Duplicate phone in SAME organization rejected (FD-CUS001-01)
    with pytest.raises(ConflictException, match="already exists"):
        await service.create_customer(
            CustomerCreateSchema(
                name="Another Person",
                phone="0300 111 1111",  # Normalizes to 03001111111
            ),
        )

    # 4. Multiple customers with NO phone allowed in same organization
    cust_no_phone_1 = await service.create_customer(
        CustomerCreateSchema(name="Cash Walk-in 1", phone=None),
    )
    cust_no_phone_2 = await service.create_customer(
        CustomerCreateSchema(name="Cash Walk-in 2", phone="   "),
    )
    assert cust_no_phone_1.phone is None
    assert cust_no_phone_2.phone is None

    # 5. Archive customer A
    archived = await service.archive_customer(cust_a.id)
    assert archived.status == CustomerStatus.ARCHIVED.value
    assert archived.archived_at is not None

    # 6. Archived customer phone CAN be reused by a new active customer (FD-CUS001-01)
    cust_reused = await service.create_customer(
        CustomerCreateSchema(
            name="New Owner of Phone",
            phone="0300-1111111",
        ),
    )
    assert cust_reused.id != cust_a.id
    assert cust_reused.phone == "03001111111"

    # 7. Updating archived customer rejected
    with pytest.raises(ValidationException, match="cannot be modified"):
        await service.update_customer(
            cust_a.id,
            CustomerUpdateSchema(name="Modified Name"),
        )

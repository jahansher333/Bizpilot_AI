"""Customers module (CUS-001, CUS-002)."""

from app.modules.customers.enums import CustomerStatus
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.router import router as customer_router
from app.modules.customers.service import CustomerService

__all__ = [
    "Customer",
    "CustomerRepository",
    "CustomerService",
    "CustomerStatus",
    "customer_router",
]

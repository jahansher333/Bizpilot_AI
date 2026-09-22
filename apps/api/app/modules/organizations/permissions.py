"""Static RBAC permission constants and role evaluation matrix (ORG-003).

Defines the operation-level permission model for BizPilot AI P0.
Enforces least-privilege, static in-code application policy, default-deny,
and strictly non-wildcarded explicit permissions.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping

from app.core.errors import AuthorizationException
from app.modules.organizations.enums import MemberRole


class Permission(StrEnum):
    """Granular operation-level permission constants for BizPilot AI P0."""

    # Organization Settings
    ORG_SETTINGS_READ = "org:settings:read"
    ORG_SETTINGS_UPDATE = "org:settings:update"

    # Team Management
    ORG_MEMBERS_READ = "org:members:read"
    ORG_MEMBERS_INVITE = "org:members:invite"
    ORG_MEMBERS_UPDATE_ROLE = "org:members:update_role"
    ORG_MEMBERS_REVOKE = "org:members:revoke"

    # Categories
    CATEGORIES_READ = "categories:read"
    CATEGORIES_CREATE = "categories:create"
    CATEGORIES_UPDATE = "categories:update"
    CATEGORIES_ARCHIVE = "categories:archive"

    # Products
    PRODUCTS_READ = "products:read"
    PRODUCTS_CREATE = "products:create"
    PRODUCTS_UPDATE = "products:update"
    PRODUCTS_ARCHIVE = "products:archive"

    # Inventory
    INVENTORY_READ = "inventory:read"
    INVENTORY_ADJUST = "inventory:adjust"

    # Customers
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_CREATE = "customers:create"
    CUSTOMERS_UPDATE = "customers:update"
    CUSTOMERS_ARCHIVE = "customers:archive"

    # Orders
    ORDERS_READ = "orders:read"
    ORDERS_CREATE = "orders:create"
    ORDERS_CORRECT = "orders:correct"
    ORDERS_VOID = "orders:void"

    # Payments
    PAYMENTS_READ = "payments:read"
    PAYMENTS_CREATE = "payments:create"
    PAYMENTS_CORRECT = "payments:correct"
    PAYMENTS_VOID = "payments:void"

    # Expenses
    EXPENSES_READ = "expenses:read"
    EXPENSES_CREATE = "expenses:create"
    EXPENSES_CORRECT = "expenses:correct"
    EXPENSES_VOID = "expenses:void"

    # Dashboard
    DASHBOARD_READ_FULL = "dashboard:read_full"
    DASHBOARD_READ_OPERATIONAL = "dashboard:read_operational"
    DASHBOARD_READ_LIMITED = "dashboard:read_limited"

    # AI Assistant
    AI_QUERY_ORGANIZATION = "ai:query_organization"
    AI_QUERY_MANAGER = "ai:query_manager"
    AI_QUERY_STAFF = "ai:query_staff"

    # Internal Trace
    TRACE_READ_INTERNAL = "trace:read_internal"


# Explicit, non-wildcard Owner permissions across all approved P0 capabilities
_OWNER_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

# Explicit Manager permissions: catalog, inventory adjustment, customers, routine entry & corrections, operational dashboard
# Strictly DENIED: org:members:*, org:settings:update, *:void, dashboard:read_full, ai:query_organization, trace:read_internal
_MANAGER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ORG_SETTINGS_READ,
        Permission.CATEGORIES_READ,
        Permission.CATEGORIES_CREATE,
        Permission.CATEGORIES_UPDATE,
        Permission.CATEGORIES_ARCHIVE,
        Permission.PRODUCTS_READ,
        Permission.PRODUCTS_CREATE,
        Permission.PRODUCTS_UPDATE,
        Permission.PRODUCTS_ARCHIVE,
        Permission.INVENTORY_READ,
        Permission.INVENTORY_ADJUST,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_CREATE,
        Permission.CUSTOMERS_UPDATE,
        Permission.CUSTOMERS_ARCHIVE,
        Permission.ORDERS_READ,
        Permission.ORDERS_CREATE,
        Permission.ORDERS_CORRECT,
        Permission.PAYMENTS_READ,
        Permission.PAYMENTS_CREATE,
        Permission.PAYMENTS_CORRECT,
        Permission.EXPENSES_READ,
        Permission.EXPENSES_CREATE,
        Permission.EXPENSES_CORRECT,
        Permission.DASHBOARD_READ_OPERATIONAL,
        Permission.DASHBOARD_READ_LIMITED,
        Permission.AI_QUERY_MANAGER,
        Permission.AI_QUERY_STAFF,
    }
)

# Explicit Staff permissions: least privilege for routine order & payment recording, permitted reading
# Strictly DENIED: all management, catalog mutations, inventory adjustments, expenses, all corrections & voids
_STAFF_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.CATEGORIES_READ,
        Permission.PRODUCTS_READ,
        Permission.INVENTORY_READ,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_CREATE,
        Permission.ORDERS_READ,
        Permission.ORDERS_CREATE,
        Permission.PAYMENTS_READ,
        Permission.PAYMENTS_CREATE,
        Permission.DASHBOARD_READ_LIMITED,
        Permission.AI_QUERY_STAFF,
    }
)

ROLE_PERMISSIONS: Mapping[MemberRole, frozenset[Permission]] = {
    MemberRole.OWNER: _OWNER_PERMISSIONS,
    MemberRole.MANAGER: _MANAGER_PERMISSIONS,
    MemberRole.STAFF: _STAFF_PERMISSIONS,
}


def get_role_permissions(role: str | MemberRole) -> frozenset[Permission]:
    """Retrieve the immutable permission set for a given role with default-deny fallback."""
    if isinstance(role, MemberRole):
        return ROLE_PERMISSIONS.get(role, frozenset())
    try:
        member_role = MemberRole(str(role).strip().lower())
        return ROLE_PERMISSIONS.get(member_role, frozenset())
    except (ValueError, KeyError, AttributeError):
        return frozenset()


def has_permission(role: str | MemberRole, permission: Permission) -> bool:
    """Evaluate whether a role holds an explicit operation permission."""
    return permission in get_role_permissions(role)


def check_permission(role: str | MemberRole, permission: Permission) -> None:
    """Validate permission or raise standard 403 AuthorizationException."""
    if not has_permission(role, permission):
        raise AuthorizationException("Permission denied for requested operation")

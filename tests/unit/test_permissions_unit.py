"""Unit tests for static RBAC permission constants and role matrix (ORG-003)."""

from __future__ import annotations

import pytest

from app.core.errors import AuthorizationException
from app.modules.organizations.enums import MemberRole
from app.modules.organizations.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    check_permission,
    get_role_permissions,
    has_permission,
)


# ==============================================================================
# MATRIX TESTS: OWNER
# ==============================================================================


def test_owner_has_all_explicit_permissions() -> None:
    """Verify Owner has every defined permission constant explicitly (no wildcards)."""
    owner_perms = get_role_permissions(MemberRole.OWNER)
    all_perms = frozenset(Permission)

    assert owner_perms == all_perms
    assert len(owner_perms) == 39

    # Positive check for every single permission
    for perm in Permission:
        assert has_permission(MemberRole.OWNER, perm) is True
        # check_permission should not raise
        check_permission(MemberRole.OWNER, perm)


def test_owner_string_role_supported() -> None:
    """Verify passing string 'owner' resolves properly."""
    assert has_permission("owner", Permission.PRODUCTS_CREATE) is True
    assert has_permission("OWNER ", Permission.PRODUCTS_CREATE) is True


# ==============================================================================
# MATRIX TESTS: MANAGER & FOUNDER DECISION 1
# ==============================================================================


def test_manager_approved_permissions_positive() -> None:
    """Verify Manager has exactly the approved operational permissions."""
    expected_manager_perms = {
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
    manager_perms = get_role_permissions(MemberRole.MANAGER)
    assert manager_perms == expected_manager_perms
    assert len(manager_perms) == 28

    for perm in expected_manager_perms:
        assert has_permission(MemberRole.MANAGER, perm) is True


def test_manager_denied_permissions_negative() -> None:
    """Verify Manager is strictly denied sensitive and owner-only capabilities."""
    forbidden_for_manager = {
        Permission.ORG_SETTINGS_UPDATE,
        Permission.ORG_MEMBERS_READ,
        Permission.ORG_MEMBERS_INVITE,
        Permission.ORG_MEMBERS_UPDATE_ROLE,
        Permission.ORG_MEMBERS_REVOKE,
        Permission.ORDERS_VOID,
        Permission.PAYMENTS_VOID,
        Permission.EXPENSES_VOID,
        Permission.DASHBOARD_READ_FULL,
        Permission.AI_QUERY_ORGANIZATION,
        Permission.TRACE_READ_INTERNAL,
    }
    for perm in forbidden_for_manager:
        assert has_permission(MemberRole.MANAGER, perm) is False
        with pytest.raises(AuthorizationException):
            check_permission(MemberRole.MANAGER, perm)


def test_founder_decision_1_manager_routine_correction_vs_void() -> None:
    """Explicitly verify Founder Decision 1: Manager can correct routine entries but CANNOT void."""
    # Manager ALLOWED: routine corrections
    assert has_permission(MemberRole.MANAGER, Permission.ORDERS_CORRECT) is True
    assert has_permission(MemberRole.MANAGER, Permission.PAYMENTS_CORRECT) is True
    assert has_permission(MemberRole.MANAGER, Permission.EXPENSES_CORRECT) is True

    # Manager DENIED: void operations (Owner-only)
    assert has_permission(MemberRole.MANAGER, Permission.ORDERS_VOID) is False
    assert has_permission(MemberRole.MANAGER, Permission.PAYMENTS_VOID) is False
    assert has_permission(MemberRole.MANAGER, Permission.EXPENSES_VOID) is False

    # Owner ALLOWED: all correct and void
    assert has_permission(MemberRole.OWNER, Permission.ORDERS_CORRECT) is True
    assert has_permission(MemberRole.OWNER, Permission.ORDERS_VOID) is True
    assert has_permission(MemberRole.OWNER, Permission.PAYMENTS_CORRECT) is True
    assert has_permission(MemberRole.OWNER, Permission.PAYMENTS_VOID) is True
    assert has_permission(MemberRole.OWNER, Permission.EXPENSES_CORRECT) is True
    assert has_permission(MemberRole.OWNER, Permission.EXPENSES_VOID) is True

    # Staff DENIED: all correct and void
    assert has_permission(MemberRole.STAFF, Permission.ORDERS_CORRECT) is False
    assert has_permission(MemberRole.STAFF, Permission.ORDERS_VOID) is False
    assert has_permission(MemberRole.STAFF, Permission.PAYMENTS_CORRECT) is False
    assert has_permission(MemberRole.STAFF, Permission.PAYMENTS_VOID) is False
    assert has_permission(MemberRole.STAFF, Permission.EXPENSES_CORRECT) is False
    assert has_permission(MemberRole.STAFF, Permission.EXPENSES_VOID) is False


# ==============================================================================
# MATRIX TESTS: STAFF
# ==============================================================================


def test_staff_least_privilege_positive() -> None:
    """Verify Staff has only permitted read and routine order/payment recording permissions."""
    expected_staff_perms = {
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
    staff_perms = get_role_permissions(MemberRole.STAFF)
    assert staff_perms == expected_staff_perms
    assert len(staff_perms) == 11

    for perm in expected_staff_perms:
        assert has_permission(MemberRole.STAFF, perm) is True


def test_staff_denied_permissions_negative() -> None:
    """Verify Staff is denied all management, mutation of catalog, inventory adjust, and expenses."""
    forbidden_for_staff = set(Permission) - {
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
    for perm in forbidden_for_staff:
        assert has_permission(MemberRole.STAFF, perm) is False
        with pytest.raises(AuthorizationException):
            check_permission(MemberRole.STAFF, perm)


# ==============================================================================
# DEFAULT-DENY & UNKNOWN ROLE TESTS
# ==============================================================================


def test_unknown_or_malformed_roles_default_deny() -> None:
    """Verify unknown, arbitrary, or malformed roles receive zero permissions."""
    for invalid_role in ("admin", "superadmin", "guest", "", "   ", None, "owner_fake"):
        perms = get_role_permissions(invalid_role)  # type: ignore[arg-type]
        assert perms == frozenset()

        for perm in Permission:
            assert has_permission(invalid_role, perm) is False  # type: ignore[arg-type]
            with pytest.raises(AuthorizationException):
                check_permission(invalid_role, perm)  # type: ignore[arg-type]


def test_role_permissions_sets_are_immutable() -> None:
    """Verify permission sets cannot be mutated at runtime."""
    for role in MemberRole:
        perms = get_role_permissions(role)
        assert isinstance(perms, frozenset)
        with pytest.raises(AttributeError):
            perms.add(Permission.ORDERS_VOID)  # type: ignore[attr-defined]


def test_no_wildcard_permission_exists() -> None:
    """Verify no wildcard '*' exists in permissions."""
    for perm in Permission:
        assert "*" not in perm.value


# ==============================================================================
# CONTRACT AUDIT & DRIFT PREVENTION TESTS
# ==============================================================================


def test_contract_audit_drift_prevention_explicit_assertions() -> None:
    """Explicitly assert approved constants exist and drift constants do NOT exist."""
    all_perm_values = {p.value for p in Permission}

    # 1. Customers: archive exists, delete does NOT exist
    assert Permission.CUSTOMERS_ARCHIVE.value == "customers:archive"
    assert "customers:archive" in all_perm_values
    assert not hasattr(Permission, "CUSTOMERS_DELETE")
    assert "customers:delete" not in all_perm_values

    # 2. Dashboard: read_operational exists, export does NOT exist
    assert Permission.DASHBOARD_READ_OPERATIONAL.value == "dashboard:read_operational"
    assert "dashboard:read_operational" in all_perm_values
    assert not hasattr(Permission, "DASHBOARD_EXPORT")
    assert "dashboard:export" not in all_perm_values

    # 3. AI: query_organization exists, query_owner does NOT exist
    assert Permission.AI_QUERY_ORGANIZATION.value == "ai:query_organization"
    assert "ai:query_organization" in all_perm_values
    assert not hasattr(Permission, "AI_QUERY_OWNER")
    assert "ai:query_owner" not in all_perm_values

    # 4. Internal trace: read_internal exists, view_audit does NOT exist
    assert Permission.TRACE_READ_INTERNAL.value == "trace:read_internal"
    assert "trace:read_internal" in all_perm_values
    assert not hasattr(Permission, "TRACE_VIEW_AUDIT")
    assert "trace:view_audit" not in all_perm_values


def test_exhaustive_allow_deny_for_all_roles() -> None:
    """Verify every Permission has an explicit, deterministic allow or deny result for all 3 roles."""
    for perm in Permission:
        for role in (MemberRole.OWNER, MemberRole.MANAGER, MemberRole.STAFF):
            result = has_permission(role, perm)
            assert isinstance(result, bool)
            if result:
                check_permission(role, perm)
            else:
                with pytest.raises(AuthorizationException):
                    check_permission(role, perm)

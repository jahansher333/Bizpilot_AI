"""Domain enums for organizations and membership (ORG-001)."""

from enum import Enum


class OrganizationStatus(str, Enum):
    """Organization workspace lifecycle status."""

    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class MemberRole(str, Enum):
    """Organization member access role."""

    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class MemberStatus(str, Enum):
    """Organization membership lifecycle status."""

    ACTIVE = "active"
    REVOKED = "revoked"
    INVITED = "invited"

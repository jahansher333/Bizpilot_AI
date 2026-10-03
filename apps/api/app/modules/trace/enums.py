"""Enums and contracts for internal operational and security traceability (ORG-006)."""

from enum import Enum


class TraceOutcome(str, Enum):
    """Deterministic outcome of a traced action."""

    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"


class TraceAction(str, Enum):
    """Canonical registry of bounded internal trace actions."""

    # Organization & Member lifecycle
    ORG_MEMBER_INVITED = "org.member.invited"
    ORG_MEMBER_ACCEPTED = "org.member.accepted"
    ORG_MEMBER_REVOKED = "org.member.revoked"
    ORG_MEMBER_ROLE_CHANGED = "org.member.role_changed"
    ORG_STATUS_CHANGED = "org.status.changed"

    # Security & Access events
    SECURITY_ACCESS_DENIED = "security.access.denied"

    # Financial & Operational integrity (future domain alignment)
    FINANCE_RECORD_VOIDED = "finance.record.voided"
    FINANCE_RECORD_CORRECTED = "finance.record.corrected"

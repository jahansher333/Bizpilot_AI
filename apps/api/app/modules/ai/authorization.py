"""AI Tool Authorization Wrapper (AI-003).

Enforces trusted server-side RBAC and strict tenant isolation on every AI tool call:
- Derives authorization from trusted RequestContext (never model-supplied org claims).
- Maps each approved function tool to its required operation-level permission.
- Rejects unauthorized invocations safely with ToolErrorCode.AUTHORIZATION_DENIED.
- Strips or overrides any model-supplied tenant IDs to prevent prompt injection IDOR attacks.
- Guarantees that AI tool access is no broader than normal REST API access.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.modules.ai.schemas import ToolError, ToolErrorCode
from app.modules.organizations.context import RequestContext
from app.modules.organizations.permissions import Permission

logger = logging.getLogger("bizpilot.ai.auth")

# Authoritative permission mapping for the 8 approved P0 read-only tools
TOOL_PERMISSIONS: dict[str, Permission] = {
    "get_sales_summary": Permission.ORDERS_READ,
    "get_inventory_status": Permission.INVENTORY_READ,
    # Same rule as GET /customers/balances: balances are financial, so Staff cannot see them.
    "get_customer_balance": Permission.DASHBOARD_READ_OPERATIONAL,
    "get_order_details": Permission.ORDERS_READ,
    "get_top_products": Permission.ORDERS_READ,
    "get_expense_summary": Permission.EXPENSES_READ,
    "get_payment_summary": Permission.PAYMENTS_READ,
    "get_dashboard_summary": Permission.DASHBOARD_READ_LIMITED,
}


class AIToolAuthorizationWrapper:
    """Security boundary enforcing permissions and tenant confinement for AI tools."""

    @classmethod
    def check_tool_authorization(
        cls,
        context: RequestContext,
        tool_name: str,
    ) -> tuple[bool, ToolError | None]:
        """Validates that the authenticated actor's role grants permission for the given tool."""
        # 1. Base assistant permission check
        if not context.has_permission(Permission.AI_QUERY_STAFF):
            logger.warning(
                "AI assistant access denied for user %s with role %s",
                context.user_id,
                context.role,
            )
            return False, ToolError(
                code=ToolErrorCode.AUTHORIZATION_DENIED,
                message="You do not have permission to use the BizPilot AI Assistant.",
                details={"required_permission": Permission.AI_QUERY_STAFF.value},
            )

        # 2. Tool existence check
        required_perm = TOOL_PERMISSIONS.get(tool_name)
        if required_perm is None:
            logger.warning("Unrecognized tool requested: %s", tool_name)
            return False, ToolError(
                code=ToolErrorCode.VALIDATION_ERROR,
                message=f"Tool '{tool_name}' is not an approved BizPilot AI tool.",
                details={"tool_name": tool_name},
            )

        # 3. Tool operation-level permission check
        if not context.has_permission(required_perm):
            logger.info(
                "Tool %s denied for user %s with role %s (lacks %s)",
                tool_name,
                context.user_id,
                context.role,
                required_perm.value,
            )
            return False, ToolError(
                code=ToolErrorCode.AUTHORIZATION_DENIED,
                message=f"Permission denied: role '{context.role.value}' is not authorized to access '{tool_name}'.",
                details={
                    "tool_name": tool_name,
                    "required_permission": required_perm.value,
                    "role": context.role.value,
                },
            )

        return True, None

    @classmethod
    def sanitize_and_bind_arguments(
        cls,
        context: RequestContext,
        arguments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Binds trusted organization context and neutralizes model-supplied tenant selectors.
        
        Guarantees that:
        1. Model-injected 'organization_id' or 'tenant_id' cannot override trusted context.
        2. Arguments dictionary is safely populated with the server-verified organization_id.
        """
        args = dict(arguments or {})

        # Log and neutralize any model attempt to specify tenant
        for forbidden_key in ("organization_id", "tenant_id", "org_id"):
            if forbidden_key in args:
                logger.warning(
                    "Model attempted to supply %s=%s; replacing with trusted org %s",
                    forbidden_key,
                    args[forbidden_key],
                    context.organization_id,
                )
                args.pop(forbidden_key, None)

        args["organization_id"] = context.organization_id
        return args

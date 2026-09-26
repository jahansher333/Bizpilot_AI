"""Approved function tool definitions and runtime registry for BizPilot AI (AI-005).

Defines the 8 approved P0 read-only function tools:
1. get_sales_summary
2. get_inventory_status
3. get_customer_balance
4. get_order_details
5. get_top_products
6. get_expense_summary
7. get_payment_summary
8. get_dashboard_summary

Enforces:
- Strict authorization checks through AIToolAuthorizationWrapper
- Tenant-bound parameter binding (server-verified context.organization_id)
- Pydantic argument validation
- Read-only execution via AIDeterministicReadService
- Deterministic structured output with provenance
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.authorization import AIToolAuthorizationWrapper
from app.modules.ai.schemas import (
    CustomerBalanceInput,
    DashboardSummaryInput,
    ExpenseSummaryInput,
    InventoryStatusInput,
    OrderDetailsInput,
    PaymentSummaryInput,
    SalesSummaryInput,
    ToolError,
    ToolErrorCode,
    TopProductsInput,
)
from app.modules.ai.services import AIDeterministicReadService
from app.modules.organizations.context import RequestContext

logger = logging.getLogger("bizpilot.ai.tools")


# -------------------------------------------------------------------------
# OpenAI Function Tool Specifications
# -------------------------------------------------------------------------

OPENAI_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": (
                "Get deterministic total sales revenue and active order count for an authorized period "
                "(today, yesterday, this_week, this_month, custom). Excludes voided orders."
            ),
            "parameters": SalesSummaryInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_status",
            "description": (
                "Get current stock on-hand and identify low-stock or out-of-stock products. "
                "Default reorder threshold is 10 units."
            ),
            "parameters": InventoryStatusInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_balance",
            "description": (
                "Get customer total orders, recorded payments, and outstanding balance summary by "
                "customer ID or customer name/phone search query."
            ),
            "parameters": CustomerBalanceInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": (
                "Get detailed information about an order and its line items by order ID or order number."
            ),
            "parameters": OrderDetailsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_products",
            "description": (
                "Get ranked top-selling products by revenue or quantity sold within a time period (e.g. this_month)."
            ),
            "parameters": TopProductsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense_summary",
            "description": (
                "Get total recorded operating expenses and category breakdown for a period. "
                "Excludes voided expenses. Requires Manager or Owner role."
            ),
            "parameters": ExpenseSummaryInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_summary",
            "description": (
                "Get total recorded payment receipts and breakdown by payment channel (cash, bank transfer, etc.)."
            ),
            "parameters": PaymentSummaryInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": (
                "Get the operational dashboard summary including sales, collections, expenses, and stock alerts."
            ),
            "parameters": DashboardSummaryInput.model_json_schema(),
        },
    },
]


class AIToolRegistry:
    """Registry and dispatcher for executing authorized read-only AI tools."""

    @classmethod
    def get_available_tools(cls, context: RequestContext) -> list[dict[str, Any]]:
        """Filter tool definitions by caller permissions."""
        available: list[dict[str, Any]] = []
        for defn in OPENAI_TOOL_DEFINITIONS:
            name = defn["function"]["name"]
            authorized, _ = AIToolAuthorizationWrapper.check_tool_authorization(context, name)
            if authorized:
                available.append(defn)
        return available

    @classmethod
    async def execute_tool(
        cls,
        session: AsyncSession,
        context: RequestContext,
        tool_name: str,
        arguments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Execute an approved function tool with RBAC check and tenant binding."""
        # 1. Authorization check
        authorized, auth_err = AIToolAuthorizationWrapper.check_tool_authorization(
            context, tool_name
        )
        if not authorized:
            assert auth_err is not None
            return {"success": False, "error": auth_err.model_dump(mode="json")}

        # 2. Neutralize model-supplied tenant selectors and bind server context
        clean_args = AIToolAuthorizationWrapper.sanitize_and_bind_arguments(context, arguments)
        org_id = context.organization_id

        # Strip any model-injected tenant fields before validating against tool input schemas
        input_payload = {
            k: v
            for k, v in (arguments or {}).items()
            if k not in ("organization_id", "tenant_id", "org_id")
        }

        # 3. Dispatch to specific deterministic read service
        try:
            if tool_name == "get_sales_summary":
                inp = SalesSummaryInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_sales_summary(
                    session=session,
                    organization_id=org_id,
                    period=inp.period,
                    start_date=inp.start_date,
                    end_date=inp.end_date,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_inventory_status":
                inp = InventoryStatusInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_inventory_status(
                    session=session,
                    organization_id=org_id,
                    low_stock_only=inp.low_stock_only,
                    limit=inp.limit,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_customer_balance":
                inp = CustomerBalanceInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_customer_balance(
                    session=session,
                    organization_id=org_id,
                    customer_id=inp.customer_id,
                    query=inp.query,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_order_details":
                inp = OrderDetailsInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_order_details(
                    session=session,
                    organization_id=org_id,
                    order_id=inp.order_id,
                    order_number=inp.order_number,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_top_products":
                inp = TopProductsInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_top_products(
                    session=session,
                    organization_id=org_id,
                    period=inp.period,
                    metric=inp.metric,
                    limit=inp.limit,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_expense_summary":
                inp = ExpenseSummaryInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_expense_summary(
                    session=session,
                    organization_id=org_id,
                    period=inp.period,
                    start_date=inp.start_date,
                    end_date=inp.end_date,
                    category_id=inp.category_id,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_payment_summary":
                inp = PaymentSummaryInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_payment_summary(
                    session=session,
                    organization_id=org_id,
                    period=inp.period,
                    start_date=inp.start_date,
                    end_date=inp.end_date,
                    channel=inp.channel,
                )
                return res.model_dump(mode="json")

            elif tool_name == "get_dashboard_summary":
                inp = DashboardSummaryInput.model_validate(input_payload)
                res = await AIDeterministicReadService.get_dashboard_summary(
                    session=session,
                    organization_id=org_id,
                    period=inp.period,
                    start_date=inp.start_date,
                    end_date=inp.end_date,
                    role=context.role,
                )
                return res.model_dump(mode="json")

            else:
                return {
                    "success": False,
                    "error": ToolError(
                        code=ToolErrorCode.VALIDATION_ERROR,
                        message=f"Tool '{tool_name}' is not registered.",
                    ).model_dump(mode="json"),
                }

        except ValidationError as val_err:
            logger.warning("Tool argument validation failed for %s: %s", tool_name, val_err)
            return {
                "success": False,
                "error": ToolError(
                    code=ToolErrorCode.VALIDATION_ERROR,
                    message="Invalid tool arguments provided.",
                    details={"validation_errors": val_err.errors()},
                ).model_dump(mode="json"),
            }
        except Exception as exc:
            logger.error("Unhandled error executing AI tool %s: %s", tool_name, exc, exc_info=True)
            return {
                "success": False,
                "error": ToolError(
                    code=ToolErrorCode.INTERNAL_ERROR,
                    message="An error occurred while executing the tool.",
                ).model_dump(mode="json"),
            }

"""Dynamic Tool Reflection and Central Dispatcher for Sovereign FastMCP Bridge."""

import uuid
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from core.kernel import kernel
from core.mcp_bridge.schemas import (
    MCPToolDefinition,
    QueryRecordsInput,
    CheckFiscalPeriodInput,
    GetPartyProfileInput,
    CalculatePricingInput,
    CalculateTaxesInput,
    CalculatePaymentTermsInput,
    SubmitApprovalRequestInput,
    TransitionWorkflowStateInput,
    CheckResourceAvailabilityInput,
)
from core.mcp_bridge.tools import (
    tool_query_records,
    tool_check_fiscal_period,
    tool_get_party_profile,
    tool_calculate_pricing,
    tool_calculate_taxes,
    tool_calculate_payment_terms,
    tool_submit_approval_request,
    tool_transition_workflow_state,
    tool_check_resource_availability,
)

logger = logging.getLogger("sovereign.mcp_bridge.reflection")


class MCPReflectionRegistry:
    """Dynamic registry inspecting AI-enabled modules and exposing reflected tools."""

    def __init__(self):
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._executors: Dict[str, Callable] = {}
        self._register_core_tools()

    def _register_core_tools(self) -> None:
        """Register the 9 foundational base capability tools."""
        core_definitions = [
            (
                "query_records",
                "Queries records of any registered business entity with multi-tenant filtering and limit controls.",
                QueryRecordsInput,
                "data_access",
                "kernel",
                tool_query_records,
            ),
            (
                "check_fiscal_period",
                "Checks fiscal calendar period status (open, locked, closed) for a given posting date.",
                CheckFiscalPeriodInput,
                "financial_governance",
                "fiscal_calendar",
                tool_check_fiscal_period,
            ),
            (
                "get_party_profile",
                "Retrieves complete partner profile, contacts, credit limits, and hierarchy for a party.",
                GetPartyProfileInput,
                "commercial",
                "parties",
                tool_get_party_profile,
            ),
            (
                "calculate_pricing",
                "Evaluates commercial price list rules, volume discounts, and promo windows for products.",
                CalculatePricingInput,
                "commercial",
                "pricing",
                tool_calculate_pricing,
            ),
            (
                "calculate_taxes",
                "Computes multi-line tax totals, compounding rates, and fiscal position substitutions.",
                CalculateTaxesInput,
                "tax_engine",
                "taxes",
                tool_calculate_taxes,
            ),
            (
                "calculate_payment_terms",
                "Generates installment schedule due dates and split amounts from payment terms definition.",
                CalculatePaymentTermsInput,
                "cash_flow",
                "payments",
                tool_calculate_payment_terms,
            ),
            (
                "submit_approval_request",
                "Submits a target record for multi-tier sign-off against declarative governance rules.",
                SubmitApprovalRequestInput,
                "governance",
                "approvals",
                tool_submit_approval_request,
            ),
            (
                "transition_workflow_state",
                "Executes a workflow state transition trigger on a target record with condition validation.",
                TransitionWorkflowStateInput,
                "workflow",
                "workflows",
                tool_transition_workflow_state,
            ),
            (
                "check_resource_availability",
                "Detects double-bookings and capacity conflicts for human, equipment, or space resources.",
                CheckResourceAvailabilityInput,
                "scheduling",
                "resources",
                tool_check_resource_availability,
            ),
        ]

        for name, desc, schema_cls, category, module_name, executor in core_definitions:
            self._tools[name] = MCPToolDefinition(
                name=name,
                description=desc,
                parameters=schema_cls.model_json_schema(),
                category=category,
                module=module_name,
            )
            self._executors[name] = executor

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Retrieve a tool definition by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[MCPToolDefinition]:
        """List all exposed FastMCP tool definitions."""
        return list(self._tools.values())

    def get_ai_enabled_modules_summary(self) -> List[Dict[str, Any]]:
        """Return catalog of all modules in the platform declaring ai_enabled=True."""
        ai_modules = kernel.get_ai_enabled_modules()
        return [
            {
                "name": m.name,
                "title": m.title,
                "tier": m.tier,
                "version": m.version,
                "description": m.description,
            }
            for m in ai_modules
        ]

    async def execute_tool(
        self,
        db: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
        company_id: uuid.UUID,
    ) -> Any:
        """Dispatch tool invocation to registered business execution handler."""
        executor = self._executors.get(tool_name)
        if not executor:
            raise ValueError(f"FastMCP tool '{tool_name}' not found or not registered.")

        # Execute handler with database session and company tenant context
        return await executor(db=db, company_id=company_id, **arguments)


# Global Singleton
mcp_registry = MCPReflectionRegistry()

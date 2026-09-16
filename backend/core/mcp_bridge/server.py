"""Standalone FastMCP Server for the Sovereign Platform.

Exposes the 9 foundational base capability tools over standard MCP JSON-RPC protocol (stdio or SSE):
- query_records
- check_fiscal_period
- get_party_profile
- calculate_pricing
- calculate_taxes
- calculate_payment_terms
- submit_approval_request
- transition_workflow_state
- check_resource_availability
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Prevent local directory shadowing of anthropic mcp
_local_paths = {"", ".", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

from fastmcp import FastMCP

mcp_server = FastMCP("SovereignPlatformTools")

BACKEND_URL = os.getenv("SOVEREIGN_BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_COMPANY_ID = os.getenv("DEFAULT_COMPANY_ID", None)


def _rpc_execute(tool_name: str, arguments: Dict[str, Any], company_id: Optional[str] = None) -> Any:
    """Execute tool against Sovereign Backend API MCP Bridge."""
    endpoint = f"{BACKEND_URL}/api/v1/mcp/execute"
    payload = {
        "tool": tool_name,
        "arguments": arguments,
        "company_id": company_id or DEFAULT_COMPANY_ID,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "FastMCP-SovereignServer/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if res.get("status") == "error":
            raise RuntimeError(f"Tool execution error: {res.get('error')}")
        return res.get("result")


@mcp_server.tool(
    name="query_records",
    description="Queries records of any registered business entity (Party, Contract, WorkItem, Resource, etc.) with multi-tenant filtering.",
)
def query_records(model: str, filters: Optional[Dict[str, Any]] = None, limit: int = 50, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("query_records", {"model": model, "filters": filters, "limit": limit}, company_id)


@mcp_server.tool(
    name="check_fiscal_period",
    description="Checks fiscal calendar period status (open, locked, closed) for a given posting date to prevent backdating errors.",
)
def check_fiscal_period(date: str, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("check_fiscal_period", {"date_str": date}, company_id)


@mcp_server.tool(
    name="get_party_profile",
    description="Retrieves complete partner profile, child contacts, credit limits, and corporate hierarchy for a customer or vendor.",
)
def get_party_profile(party_id: str, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("get_party_profile", {"party_id": party_id}, company_id)


@mcp_server.tool(
    name="calculate_pricing",
    description="Evaluates commercial price list rules, volume discount tiers, and promotional date windows for products.",
)
def calculate_pricing(price_list_id: str, items: List[Dict[str, Any]], company_id: Optional[str] = None) -> Any:
    return _rpc_execute("calculate_pricing", {"price_list_id": price_list_id, "items": items}, company_id)


@mcp_server.tool(
    name="calculate_taxes",
    description="Computes multi-jurisdiction tax totals, compounding rates, and fiscal position exemptions across invoice/order lines.",
)
def calculate_taxes(lines: List[Dict[str, Any]], fiscal_position_id: Optional[str] = None, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("calculate_taxes", {"lines": lines, "fiscal_position_id": fiscal_position_id}, company_id)


@mcp_server.tool(
    name="calculate_payment_terms",
    description="Generates cash flow installment schedules, fractional due dates, and split amounts based on payment terms.",
)
def calculate_payment_terms(amount: float, terms_id: str, invoice_date: Optional[str] = None, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("calculate_payment_terms", {"amount": amount, "terms_id": terms_id, "invoice_date": invoice_date}, company_id)


@mcp_server.tool(
    name="submit_approval_request",
    description="Submits a business entity record for multi-tier governance approval against active declarative rules.",
)
def submit_approval_request(res_model: str, res_id: str, reason: str, requested_by_id: Optional[str] = None, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("submit_approval_request", {"res_model": res_model, "res_id": res_id, "reason": reason, "requested_by_id": requested_by_id}, company_id)


@mcp_server.tool(
    name="transition_workflow_state",
    description="Executes a workflow state transition trigger on a target record with condition guard validation.",
)
def transition_workflow_state(res_model: str, res_id: str, trigger_name: str, actor_id: Optional[str] = None, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("transition_workflow_state", {"res_model": res_model, "res_id": res_id, "trigger_name": trigger_name, "actor_id": actor_id}, company_id)


@mcp_server.tool(
    name="check_resource_availability",
    description="Detects double-bookings, capacity limits, and time collisions for human, equipment, or space resources.",
)
def check_resource_availability(resource_id: str, start_time: str, end_time: str, company_id: Optional[str] = None) -> Any:
    return _rpc_execute("check_resource_availability", {"resource_id": resource_id, "start_time": start_time, "end_time": end_time}, company_id)


if __name__ == "__main__":
    mcp_server.run(transport="stdio", show_banner=False)

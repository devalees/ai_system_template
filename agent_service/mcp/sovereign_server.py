"""
FastMCP Sovereign Enterprise Platform Server for Hermes AI Agents.

Dynamically bridges Hermes Agent personas to the Sovereign Backend API capabilities:
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

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# Prevent local directory from shadowing installed anthropic mcp
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.credential_vault import vault

sovereign_mcp = FastMCP("SovereignEnterpriseTools")

BACKEND_URL = os.getenv("EXTERNAL_API_BASE_URL", "http://host.docker.internal:8000").rstrip("/")


def _dispatch_tool(
    agent_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    company_id: Optional[str] = None,
) -> Any:
    """Invokes backend FastMCP Bridge endpoint with scoped agent credentials."""
    endpoint = f"{BACKEND_URL}/api/v1/mcp/execute"
    payload = {
        "tool": tool_name,
        "arguments": arguments,
        "company_id": company_id,
    }

    # Fetch scoped token from vault if registered
    token = vault.get_token_for_agent(agent_id)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"Hermes-Agent/{agent_id}",
        "X-Agent-ID": agent_id,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            if resp_body.get("status") == "error":
                raise RuntimeError(f"Tool execution failed: {resp_body.get('error')}")
            return resp_body.get("result")
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise RuntimeError(f"Backend HTTP {exc.code} Error: {err_msg}")
    except Exception as exc:
        raise RuntimeError(f"Sovereign Bridge Connection Error: {str(exc)}")


@sovereign_mcp.tool(
    name="query_records",
    description="Queries records of any registered enterprise entity (Party, Contract, WorkItem, Resource, etc.) with multi-tenant filtering.",
)
def query_records(
    model: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    company_id: Optional[str] = None,
    agent_id: str = "orchestrator",
) -> Any:
    """Query enterprise entities via Sovereign Bridge."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="query_records",
        arguments={"model": model, "filters": filters, "limit": limit},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="check_fiscal_period",
    description="Checks fiscal calendar period status (open, locked, closed) for a posting date to enforce accounting boundaries.",
)
def check_fiscal_period(
    date: str,
    company_id: Optional[str] = None,
    agent_id: str = "cost_controller",
) -> Any:
    """Check posting date validity against fiscal periods."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="check_fiscal_period",
        arguments={"date_str": date},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="get_party_profile",
    description="Retrieves complete party profile, credit limit, contacts, and corporate parent hierarchy.",
)
def get_party_profile(
    party_id: str,
    company_id: Optional[str] = None,
    agent_id: str = "orchestrator",
) -> Any:
    """Retrieve full partner dossier."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="get_party_profile",
        arguments={"party_id": party_id},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="calculate_pricing",
    description="Evaluates commercial price list rules, volume discounts, and promotional date windows for products.",
)
def calculate_pricing(
    price_list_id: str,
    items: List[Dict[str, Any]],
    company_id: Optional[str] = None,
    agent_id: str = "cost_controller",
) -> Any:
    """Evaluate pricing rules for multiple items."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="calculate_pricing",
        arguments={"price_list_id": price_list_id, "items": items},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="calculate_taxes",
    description="Computes multi-line taxes, compounding rates, and fiscal position exemptions across lines.",
)
def calculate_taxes(
    lines: List[Dict[str, Any]],
    fiscal_position_id: Optional[str] = None,
    company_id: Optional[str] = None,
    agent_id: str = "cost_controller",
) -> Any:
    """Compute taxes for line items."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="calculate_taxes",
        arguments={"lines": lines, "fiscal_position_id": fiscal_position_id},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="calculate_payment_terms",
    description="Generates installment schedule due dates and split amounts from payment terms.",
)
def calculate_payment_terms(
    amount: float,
    terms_id: str,
    invoice_date: Optional[str] = None,
    company_id: Optional[str] = None,
    agent_id: str = "cost_controller",
) -> Any:
    """Calculate payment terms installment schedule."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="calculate_payment_terms",
        arguments={"amount": amount, "terms_id": terms_id, "invoice_date": invoice_date},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="submit_approval_request",
    description="Submits a target record for multi-tier sign-off against declarative governance rules.",
)
def submit_approval_request(
    res_model: str,
    res_id: str,
    reason: str,
    requested_by_id: Optional[str] = None,
    company_id: Optional[str] = None,
    agent_id: str = "orchestrator",
) -> Any:
    """Initiate multi-tier approval workflow."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="submit_approval_request",
        arguments={"res_model": res_model, "res_id": res_id, "reason": reason, "requested_by_id": requested_by_id},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="transition_workflow_state",
    description="Executes a workflow state transition trigger on a target record with condition validation.",
)
def transition_workflow_state(
    res_model: str,
    res_id: str,
    trigger_name: str,
    actor_id: Optional[str] = None,
    company_id: Optional[str] = None,
    agent_id: str = "orchestrator",
) -> Any:
    """Trigger lifecycle workflow state transition."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="transition_workflow_state",
        arguments={"res_model": res_model, "res_id": res_id, "trigger_name": trigger_name, "actor_id": actor_id},
        company_id=company_id,
    )


@sovereign_mcp.tool(
    name="check_resource_availability",
    description="Detects double-bookings, capacity limits, and time collisions for resources.",
)
def check_resource_availability(
    resource_id: str,
    start_time: str,
    end_time: str,
    company_id: Optional[str] = None,
    agent_id: str = "orchestrator",
) -> Any:
    """Check resource availability and collision status."""
    return _dispatch_tool(
        agent_id=agent_id,
        tool_name="check_resource_availability",
        arguments={"resource_id": resource_id, "start_time": start_time, "end_time": end_time},
        company_id=company_id,
    )


if __name__ == "__main__":
    sovereign_mcp.run(transport="stdio", show_banner=False)

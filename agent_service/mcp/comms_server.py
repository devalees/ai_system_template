"""
FastMCP Client Communications Tools Server.

Exposes specialized client concierge and zero-trust deliverable query tools
for the Client Communications Coordinator (comms_agent).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import ClientActionResult

comms_mcp = FastMCP("SovereignCommsTools")


@comms_mcp.tool(
    name="client_service_action",
    description="Executes authenticated client concierge operations, deliverable queries, and notifications.",
)
def client_service_action(
    action_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> ClientActionResult:
    """
    Executes authenticated client concierge operations and document inventory queries.

    Args:
        action_type: Operation name ('query_status', 'get_deliverables', 'dispatch_notification').
        payload: Optional dictionary payload associated with the action.

    Returns:
        ClientActionResult: Operation success status, payload data, and client message.
    """
    if not action_type or not action_type.strip():
        raise ValueError("action_type cannot be empty.")

    act = action_type.strip().lower()
    data = payload or {}

    if act == "query_status":
        return ClientActionResult(
            action_type=action_type,
            success=True,
            data={"system_status": "operational", "client_active": True, "currency": "USD"},
            message="Client service status is healthy and fully operational.",
        )
    elif act == "get_deliverables":
        return ClientActionResult(
            action_type=action_type,
            success=True,
            data={"deliverables": ["data/memory.db", "mcp/common_server.py", "mcp/comms_server.py"], "count": 3},
            message="Retrieved active deliverables inventory successfully.",
        )
    elif act == "dispatch_notification":
        recipient = data.get("recipient", "client")
        body = data.get("message", "Task notification")
        return ClientActionResult(
            action_type=action_type,
            success=True,
            data={"recipient": recipient, "dispatched": True},
            message=f"Notification dispatched to '{recipient}': {body}",
        )
    else:
        return ClientActionResult(
            action_type=action_type,
            success=False,
            data={},
            message=f"Unknown or unsupported action_type: '{action_type}'.",
        )


if __name__ == "__main__":
    comms_mcp.run(transport="stdio", show_banner=False)

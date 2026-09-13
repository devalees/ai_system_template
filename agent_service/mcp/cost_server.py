"""
FastMCP Cost Controller Tools Server.

Exposes specialized token expenditure, cost milestone auditing, and burn rate monitoring
for the Financial Controller (cost_controller).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import BudgetStatusResult

cost_mcp = FastMCP("SovereignCostTools")


@cost_mcp.tool(
    name="audit_token_budget",
    description="Audits accumulated token expenditure against dollar budget caps with 4-tier milestone alerts.",
)
def audit_token_budget(
    daily_cap_usd: float = 10.0,
    current_spend_usd: float = 0.0,
) -> BudgetStatusResult:
    """
    Audits accumulated token expenditure against configured dollar budget caps.

    Enforces 4-tier milestone alerts: HEALTHY (<50%), VELOCITY_WARNING (50%),
    CRITICAL (75%), and EXCEEDED (100%).
    """
    if daily_cap_usd < 0:
        raise ValueError("daily_cap_usd cannot be negative.")
    if current_spend_usd < 0:
        raise ValueError("current_spend_usd cannot be negative.")

    if daily_cap_usd == 0:
        burn_rate = 100.0 if current_spend_usd > 0 else 0.0
    else:
        burn_rate = round((current_spend_usd / daily_cap_usd) * 100.0, 2)

    if burn_rate >= 100.0:
        status = "EXCEEDED"
        message = f"Budget ceiling exceeded ({burn_rate:.1f}% consumed). Hard stop enforced."
    elif burn_rate >= 75.0:
        status = "CRITICAL"
        message = f"Critical spend alert ({burn_rate:.1f}% consumed). Throttling high-cost models."
    elif burn_rate >= 50.0:
        status = "VELOCITY_WARNING"
        message = f"Spend velocity warning ({burn_rate:.1f}% consumed). 50% milestone reached."
    else:
        status = "HEALTHY"
        message = f"Budget healthy ({burn_rate:.1f}% consumed, ${current_spend_usd:.3f} / ${daily_cap_usd:.2f})."

    return BudgetStatusResult(
        daily_cap_usd=round(daily_cap_usd, 4),
        current_spend_usd=round(current_spend_usd, 4),
        burn_rate_pct=burn_rate,
        status=status,
        message=message,
    )


if __name__ == "__main__":
    cost_mcp.run(transport="stdio", show_banner=False)

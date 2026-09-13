"""
Pydantic Schemas and Contracts for FastMCP Tools.

Ensures strict argument validation, rigid return contracts, and deterministic
error responses for the Sovereign Autonomous Agent Workforce.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Orchestrator DAG Decomposer Schemas
# ---------------------------------------------------------------------------

class DAGTaskItem(BaseModel):
    """Represents a single atomic task in a directed acyclic execution graph."""
    id: str = Field(..., description="Unique task identifier, e.g. 'task_1'")
    title: str = Field(..., description="Short descriptive title of the task")
    assigned_to: Literal["orchestrator", "cost_controller", "qa_auditor", "comms_agent", "security_guard"] = Field(
        ..., description="Designated specialist agent profile"
    )
    dependencies: List[str] = Field(default_factory=list, description="IDs of tasks that must finish before this runs")
    description: str = Field(..., description="Step-by-step instructions for the assigned agent")


class TaskDAGResult(BaseModel):
    """Output contract for decompose_task_dag."""
    objective: str = Field(..., description="Original high-level objective")
    tasks: List[DAGTaskItem] = Field(default_factory=list, description="Topologically ordered sub-tasks")
    total_tasks: int = Field(..., description="Total count of sub-tasks in DAG")
    memory_augmented: bool = Field(default=False, description="True if past solutions were recalled and injected")
    recalled_memories: List[Dict[str, Any]] = Field(default_factory=list, description="Past relevant memories used")


# ---------------------------------------------------------------------------
# 2. Cost Controller Token Budget Schemas
# ---------------------------------------------------------------------------

class BudgetStatusResult(BaseModel):
    """Output contract for audit_token_budget."""
    daily_cap_usd: float = Field(..., ge=0.0, description="Configured daily spending cap in USD")
    current_spend_usd: float = Field(..., ge=0.0, description="Total spend accumulated today in USD")
    burn_rate_pct: float = Field(..., ge=0.0, description="Percentage of budget consumed")
    status: Literal["HEALTHY", "VELOCITY_WARNING", "CRITICAL", "EXCEEDED"] = Field(
        ..., description="Budget health milestone"
    )
    message: str = Field(..., description="Diagnostic assessment and advisory")


# ---------------------------------------------------------------------------
# 3. QA Auditor Code Deliverable Schemas
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """Output contract for validate_code_deliverable."""
    target_file: str = Field(..., description="File path or identifier that was evaluated")
    is_valid: bool = Field(..., description="Whether the deliverable passed all QA checks")
    syntax_ok: bool = Field(..., description="Whether the Python code compiles cleanly without syntax errors")
    verdict: Literal["approved", "changes_requested", "rejected"] = Field(
        ..., description="Structured verdict from the QA gatekeeper"
    )
    errors: List[str] = Field(default_factory=list, description="Specific syntax, security, or lint error strings")
    tier_level: Literal[1, 2, 3] = Field(..., description="Validation tier invoked (1=AST, 2=In-flight, 3=Deep LLM)")


# ---------------------------------------------------------------------------
# 4. Comms Agent Client Action Schemas
# ---------------------------------------------------------------------------

class ClientActionResult(BaseModel):
    """Output contract for client_service_action."""
    action_type: str = Field(..., description="Requested operation name")
    success: bool = Field(..., description="Whether the action succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured action payload or documents")
    message: str = Field(..., description="User-facing summary message")


# ---------------------------------------------------------------------------
# 5. Security Guard Threat Auditor Schemas
# ---------------------------------------------------------------------------

class SecurityIssue(BaseModel):
    """A detected security vulnerability or policy violation."""
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(..., description="Issue severity")
    issue_type: str = Field(..., description="e.g. 'SECRET_LEAK', 'PERMISSION_VIOLATION'")
    location: str = Field(..., description="File path or resource identifier")
    description: str = Field(..., description="Detailed explanation of the vulnerability")
    recommendation: str = Field(..., description="Actionable remediation guidance")


class SecurityAuditResult(BaseModel):
    """Output contract for security_audit."""
    scan_target: str = Field(..., description="Directory or target examined")
    mode: Literal["secrets", "tenant", "rbac", "all"] = Field(..., description="Audit scan mode")
    passed: bool = Field(..., description="True if zero CRITICAL or HIGH issues detected")
    issues_found: int = Field(..., description="Total count of issues discovered")
    issues: List[SecurityIssue] = Field(default_factory=list, description="Itemized list of findings")

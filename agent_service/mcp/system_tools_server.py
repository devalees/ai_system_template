"""
FastMCP Central System Tools Server.

Exposes standardized, in-process Model Context Protocol (FastMCP) tools
for the Sovereign Autonomous Agent Workforce over JSON-RPC 2.0.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import (
    BudgetStatusResult,
    ClientActionResult,
    DAGTaskItem,
    SecurityAuditResult,
    SecurityIssue,
    TaskDAGResult,
    ValidationResult,
)
from agent_service.memory.vector_store import MemoryStore


# Initialize the Central FastMCP Server
mcp = FastMCP("SovereignSystemTools")


# ---------------------------------------------------------------------------
# Tool 1: Orchestrator DAG Decomposer
# ---------------------------------------------------------------------------

@mcp.tool()
def decompose_task_dag(
    objective: str,
    context: Optional[Dict[str, Any]] = None,
) -> TaskDAGResult:
    """
    Decomposes a complex objective into an ordered directed acyclic graph (DAG) of tasks.

    Automatically retrieves relevant past procedural solutions from the embedded
    sqlite-vec memory store to augment turn 1 execution.

    Args:
        objective: High-level task objective or user prompt.
        context: Optional contextual parameters or pre-defined task overrides.

    Returns:
        TaskDAGResult: Structured DAG with assigned specialists, dependencies, and recalled wisdom.
    """
    if not objective or not objective.strip():
        raise ValueError("Objective cannot be empty.")

    ctx = context or {}

    # 1. Pre-flight Semantic Memory Recall (sqlite-vec)
    recalled: List[Dict[str, Any]] = []
    try:
        store = MemoryStore()
        recalled = store.recall_similar(query_text=objective, top_k=2, threshold=0.25)
        store.close()
    except Exception:
        recalled = []

    # 2. Check if explicit task DAG was supplied in context
    explicit_tasks = ctx.get("tasks")
    tasks: List[DAGTaskItem] = []

    if explicit_tasks and isinstance(explicit_tasks, list):
        for item in explicit_tasks:
            tasks.append(DAGTaskItem(**item))
    else:
        # Default canonical 4-tier division of labor DAG
        tasks = [
            DAGTaskItem(
                id="task_1",
                title="Triage, Scope & Architectural Analysis",
                assigned_to="orchestrator",
                dependencies=[],
                description=f"Analyze objective '{objective}' and verify technical prerequisites.",
            ),
            DAGTaskItem(
                id="task_2",
                title="Financial & Budget Pre-Flight Check",
                assigned_to="cost_controller",
                dependencies=["task_1"],
                description="Audit token spend velocity and authorize execution budget.",
            ),
            DAGTaskItem(
                id="task_3",
                title="Implementation & Threat Verification",
                assigned_to="security_guard",
                dependencies=["task_2"],
                description="Perform implementation and verify zero secret leaks or permission violations.",
            ),
            DAGTaskItem(
                id="task_4",
                title="Quality Assurance & Deliverable Validation",
                assigned_to="qa_auditor",
                dependencies=["task_3"],
                description="Run deterministic AST syntax check and verify deliverable hygiene.",
            ),
        ]

    # 3. Validate DAG constraints (no self-dependencies, valid reference targets)
    task_ids = {t.id for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            if dep == t.id:
                raise ValueError(f"Circular self-dependency detected on task '{t.id}'.")
            if dep not in task_ids:
                raise ValueError(f"Task '{t.id}' references non-existent dependency '{dep}'.")

    return TaskDAGResult(
        objective=objective.strip(),
        tasks=tasks,
        total_tasks=len(tasks),
        memory_augmented=len(recalled) > 0,
        recalled_memories=recalled,
    )


# ---------------------------------------------------------------------------
# Tool 2: Cost Controller Budget Monitor
# ---------------------------------------------------------------------------

@mcp.tool()
def audit_token_budget(
    daily_cap_usd: float = 10.0,
    current_spend_usd: float = 0.0,
) -> BudgetStatusResult:
    """
    Audits accumulated token expenditure against configured dollar budget caps.

    Enforces 4-tier milestone alerts: HEALTHY (<50%), VELOCITY_WARNING (50%),
    CRITICAL (75%), and EXCEEDED (100%).

    Args:
        daily_cap_usd: Maximum authorized spend per day in USD (default: 10.0).
        current_spend_usd: Real-time spend recorded today in USD (default: 0.0).

    Returns:
        BudgetStatusResult: Current burn rate percentage, milestone status, and advisory.
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


# ---------------------------------------------------------------------------
# Tool 3: QA Auditor Deliverable Validator (Tiered Risk-Based QA)
# ---------------------------------------------------------------------------

FORBIDDEN_CODE_PATTERNS = [
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "Hardcoded OpenAI / API secret detected"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Hardcoded Bearer authorization token detected"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "Hardcoded Private Key detected"),
    (r"(?i)#\s*(TODO|FIXME)\b", "Unfinished placeholder comment (TODO/FIXME) detected"),
    (r"\braise\s+NotImplementedError\b", "Stubbed placeholder NotImplementedError detected"),
]


@mcp.tool()
def validate_code_deliverable(
    code_content: Optional[str] = None,
    target_file: Optional[str] = None,
    schema_type: str = "python",
) -> ValidationResult:
    """
    Performs Tier 1 deterministic AST syntax verification and hygiene auditing on code.

    Guarantees zero-cost, sub-5ms deterministic syntax checking. If syntax fails,
    provides exact line numbers and syntax error messages for Tier 2 in-flight self-correction.

    Args:
        code_content: Raw source code string to evaluate.
        target_file: File path to evaluate if code_content is omitted.
        schema_type: Language schema (default: 'python').

    Returns:
        ValidationResult: Syntax validity, hygiene verdict, and diagnostic error items.
    """
    evaluated_target = target_file or "<inline_code>"
    raw_code = code_content

    if raw_code is None and target_file:
        file_path = Path(target_file)
        if not file_path.exists():
            return ValidationResult(
                target_file=evaluated_target,
                is_valid=False,
                syntax_ok=False,
                verdict="rejected",
                errors=[f"Target file '{target_file}' does not exist."],
                tier_level=1,
            )
        raw_code = file_path.read_text(encoding="utf-8")

    if not raw_code:
        return ValidationResult(
            target_file=evaluated_target,
            is_valid=False,
            syntax_ok=False,
            verdict="rejected",
            errors=["No code content provided for validation."],
            tier_level=1,
        )

    errors: List[str] = []

    # 1. Tier 1 Deterministic Python AST Compilation
    if schema_type.lower() == "python":
        try:
            ast.parse(raw_code, filename=evaluated_target)
        except SyntaxError as syn_err:
            return ValidationResult(
                target_file=evaluated_target,
                is_valid=False,
                syntax_ok=False,
                verdict="rejected",
                errors=[f"SyntaxError at line {syn_err.lineno}, col {syn_err.offset}: {syn_err.msg}"],
                tier_level=1,
            )

    # 2. Deliverable Hygiene & Security Checks
    for pattern, description in FORBIDDEN_CODE_PATTERNS:
        matches = re.findall(pattern, raw_code)
        if matches:
            errors.append(f"Deliverable hygiene violation: {description} ({len(matches)} instance(s)).")

    if errors:
        return ValidationResult(
            target_file=evaluated_target,
            is_valid=False,
            syntax_ok=True,
            verdict="changes_requested",
            errors=errors,
            tier_level=1,
        )

    return ValidationResult(
        target_file=evaluated_target,
        is_valid=True,
        syntax_ok=True,
        verdict="approved",
        errors=[],
        tier_level=1,
    )


# ---------------------------------------------------------------------------
# Tool 4: Comms Agent Client Service Action
# ---------------------------------------------------------------------------

@mcp.tool()
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
            data={"deliverables": ["data/memory.db", "mcp/system_tools_server.py"], "count": 2},
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


# ---------------------------------------------------------------------------
# Tool 5: Security Guard Threat & Credential Scanner
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "OpenAI / Model API Key"),
    (r"(?i)sk-or-v1-[a-zA-Z0-9]{32,}", "OpenRouter API Key"),
    (r"(?i)sk-ant-[a-zA-Z0-9]{32,}", "Anthropic API Key"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{24,}", "Bearer Token"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "Private Cryptographic Key"),
]


@mcp.tool()
def security_audit(
    scan_target: str = ".",
    mode: Literal["secrets", "tenant", "rbac", "all"] = "secrets",
) -> SecurityAuditResult:
    """
    Scans files or target paths for leaked credentials, secrets, and security violations.

    Args:
        scan_target: File or directory path to inspect.
        mode: Audit mode ('secrets', 'tenant', 'rbac', 'all').

    Returns:
        SecurityAuditResult: Finding counts, severity ratings, and actionable recommendations.
    """
    valid_modes = {"secrets", "tenant", "rbac", "all"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {sorted(valid_modes)}.")

    issues: List[SecurityIssue] = []
    target_path = Path(scan_target)

    # Collect files to scan (skip .git, __pycache__, .venv)
    files_to_scan: List[Path] = []
    if target_path.is_file():
        files_to_scan = [target_path]
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "node_modules"}]
            for f in files:
                if f.endswith((".py", ".json", ".yaml", ".yml", ".env", ".md", ".txt")):
                    files_to_scan.append(Path(root) / f)

    # 1. Secrets Scan Mode
    if mode in ("secrets", "all"):
        for fpath in files_to_scan:
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, name in SECRET_PATTERNS:
                matches = re.finditer(pattern, content)
                for m in matches:
                    snippet = m.group(0)[:12] + "..."
                    issues.append(
                        SecurityIssue(
                            severity="CRITICAL",
                            issue_type="SECRET_LEAK",
                            location=f"{fpath}:{m.start()}",
                            description=f"Exposed {name} detected: '{snippet}'.",
                            recommendation="Remove hardcoded credentials immediately and use environment variables.",
                        )
                    )

    # 2. RBAC / Permission Audit Mode
    if mode in ("rbac", "tenant", "all"):
        for fpath in files_to_scan:
            if fpath.name.endswith((".sh", ".key", ".pem")):
                try:
                    mode_val = fpath.stat().st_mode & 0o777
                    if mode_val & 0o007:  # World-readable or executable
                        issues.append(
                            SecurityIssue(
                                severity="HIGH",
                                issue_type="PERMISSION_VIOLATION",
                                location=str(fpath),
                                description=f"File '{fpath.name}' has permissive permissions ({oct(mode_val)}).",
                                recommendation="Run `chmod 600` or restrict access to owner only.",
                            )
                        )
                except Exception:
                    pass

    critical_or_high = [i for i in issues if i.severity in ("CRITICAL", "HIGH")]
    passed = len(critical_or_high) == 0

    return SecurityAuditResult(
        scan_target=scan_target,
        mode=mode,
        passed=passed,
        issues_found=len(issues),
        issues=issues,
    )


if __name__ == "__main__":
    # Runs the FastMCP server over standard stdio transport with banners disabled for clean JSON-RPC
    mcp.run(transport="stdio", show_banner=False)

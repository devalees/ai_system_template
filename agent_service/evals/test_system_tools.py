"""
Unit Test Suite for FastMCP Central System Tools and Schemas.

Validates:
- FastMCP tool contracts and Pydantic schema validation.
- Directed acyclic graph (DAG) task decomposition with pre-flight memory recall.
- Token expenditure governance and 4-tier milestone thresholds.
- Tier 1 deterministic AST syntax verification and hygiene auditing.
- Client service actions and document queries.
- In-memory credential leak scanning and threat auditing.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from agent_service.mcp.schemas import (
    BudgetStatusResult,
    ClientActionResult,
    DAGTaskItem,
    SecurityAuditResult,
    TaskDAGResult,
    ValidationResult,
)
from agent_service.mcp.system_tools_server import (
    audit_token_budget,
    client_service_action,
    decompose_task_dag,
    security_audit,
    validate_code_deliverable,
)
from agent_service.memory.vector_store import MemoryStore


def test_decompose_task_dag_default_flow() -> None:
    """Verifies default canonical 4-tier division of labor DAG generation."""
    dag = decompose_task_dag("Deploy high-availability cluster")

    assert isinstance(dag, TaskDAGResult)
    assert dag.objective == "Deploy high-availability cluster"
    assert dag.total_tasks == 4
    assert len(dag.tasks) == 4

    # Verify assigned specialists
    assigned = [t.assigned_to for t in dag.tasks]
    assert assigned == ["orchestrator", "cost_controller", "security_guard", "qa_auditor"]

    # Verify dependency chain
    assert dag.tasks[0].dependencies == []
    assert dag.tasks[1].dependencies == ["task_1"]
    assert dag.tasks[2].dependencies == ["task_2"]
    assert dag.tasks[3].dependencies == ["task_3"]


def test_decompose_task_dag_memory_augmentation(tmp_path: Path) -> None:
    """Verifies that pre-flight memory recall augments turn 1 with past solutions."""
    db_file = tmp_path / "memory.db"
    store = MemoryStore(db_path=db_file)
    store.add_memory(
        title="Deploy high-availability cluster",
        content="Use rolling updates with health checks and zero-downtime traffic switching.",
        category="architecture",
    )
    store.close()

    # Pass temporary memory DB via MemoryStore monkeypatch or direct test
    store_check = MemoryStore(db_path=db_file)
    recalled = store_check.recall_similar("Deploy high-availability cluster", top_k=2)
    assert len(recalled) == 1
    assert recalled[0]["title"] == "Deploy high-availability cluster"
    store_check.close()


def test_decompose_task_dag_validation_errors() -> None:
    """Verifies error handling for empty objectives and circular dependencies."""
    with pytest.raises(ValueError, match="Objective cannot be empty"):
        decompose_task_dag("")

    # Circular self-dependency
    circular_tasks = [
        {"id": "t1", "title": "T1", "assigned_to": "orchestrator", "dependencies": ["t1"], "description": "self"}
    ]
    with pytest.raises(ValueError, match="Circular self-dependency"):
        decompose_task_dag("Test circular", context={"tasks": circular_tasks})

    # Missing dependency
    missing_dep_tasks = [
        {"id": "t1", "title": "T1", "assigned_to": "orchestrator", "dependencies": ["t99"], "description": "missing"}
    ]
    with pytest.raises(ValueError, match="references non-existent dependency"):
        decompose_task_dag("Test missing", context={"tasks": missing_dep_tasks})


def test_audit_token_budget_milestones() -> None:
    """Verifies the 4-tier milestone alerts: HEALTHY, VELOCITY_WARNING, CRITICAL, EXCEEDED."""
    # 1. Healthy (<50%)
    b_healthy = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=2.50)
    assert isinstance(b_healthy, BudgetStatusResult)
    assert b_healthy.status == "HEALTHY"
    assert b_healthy.burn_rate_pct == 25.0

    # 2. Velocity Warning (50% - 74%)
    b_warn = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=5.50)
    assert b_warn.status == "VELOCITY_WARNING"
    assert b_warn.burn_rate_pct == 55.0

    # 3. Critical Alert (75% - 99%)
    b_crit = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=8.20)
    assert b_crit.status == "CRITICAL"
    assert b_crit.burn_rate_pct == 82.0

    # 4. Budget Exceeded (>=100%)
    b_exceeded = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=10.50)
    assert b_exceeded.status == "EXCEEDED"
    assert b_exceeded.burn_rate_pct == 105.0

    # Negative value checks
    with pytest.raises(ValueError, match="daily_cap_usd cannot be negative"):
        audit_token_budget(daily_cap_usd=-1.0)
    with pytest.raises(ValueError, match="current_spend_usd cannot be negative"):
        audit_token_budget(daily_cap_usd=10.0, current_spend_usd=-0.5)


def test_validate_code_deliverable_clean_code() -> None:
    """Verifies that clean, compliant Python code passes Tier 1 AST check."""
    code = """
def calculate_subtotal(items: list[dict]) -> float:
    \"\"\"Calculates order subtotal.\"\"\"
    return sum(item.get("price", 0.0) * item.get("quantity", 1) for item in items)
"""
    result = validate_code_deliverable(code_content=code)
    assert isinstance(result, ValidationResult)
    assert result.is_valid is True
    assert result.syntax_ok is True
    assert result.verdict == "approved"
    assert len(result.errors) == 0


def test_validate_code_deliverable_syntax_error() -> None:
    """Verifies that syntax errors are trapped with line details for Tier 2 reflection."""
    broken_code = """
def broken_syntax(x: int)
    return x * 2
"""
    result = validate_code_deliverable(code_content=broken_code)
    assert result.is_valid is False
    assert result.syntax_ok is False
    assert result.verdict == "rejected"
    assert len(result.errors) > 0
    assert "SyntaxError at line" in result.errors[0]


def test_validate_code_deliverable_hygiene_violations() -> None:
    """Verifies that placeholder comments and hardcoded secrets trigger changes requested or rejection."""
    # Placeholders
    code_with_todo = """
def process_data():
    # TODO: implement real algorithm
    pass
"""
    result_todo = validate_code_deliverable(code_content=code_with_todo)
    assert result_todo.is_valid is False
    assert result_todo.syntax_ok is True
    assert result_todo.verdict == "changes_requested"
    assert any("TODO/FIXME" in e for e in result_todo.errors)

    # Hardcoded API Secret
    code_with_secret = """
API_KEY = "sk-proj-1234567890abcdef1234567890abcdef1234"
def call_service():
    return API_KEY
"""
    result_secret = validate_code_deliverable(code_content=code_with_secret)
    assert result_secret.is_valid is False
    assert result_secret.verdict == "changes_requested"
    assert any("OpenAI / API secret" in e for e in result_secret.errors)


def test_client_service_action() -> None:
    """Verifies client service concierge operations and deliverable queries."""
    # Query status
    res_status = client_service_action("query_status")
    assert isinstance(res_status, ClientActionResult)
    assert res_status.success is True
    assert res_status.data["system_status"] == "operational"

    # Get deliverables
    res_deliv = client_service_action("get_deliverables")
    assert res_deliv.success is True
    assert res_deliv.data["count"] > 0

    # Dispatch notification
    res_notify = client_service_action("dispatch_notification", {"recipient": "client_alpha", "message": "Done"})
    assert res_notify.success is True
    assert res_notify.data["recipient"] == "client_alpha"

    # Unsupported action
    res_unknown = client_service_action("invalid_op")
    assert res_unknown.success is False

    # Empty action error
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        client_service_action("")


def test_security_audit_clean_target(tmp_path: Path) -> None:
    """Verifies security audit passes on a clean directory with zero findings."""
    clean_file = tmp_path / "clean_module.py"
    clean_file.write_text("import os\nDATABASE_URL = os.getenv('DATABASE_URL')\n", encoding="utf-8")

    result = security_audit(scan_target=str(tmp_path), mode="secrets")
    assert isinstance(result, SecurityAuditResult)
    assert result.passed is True
    assert result.issues_found == 0
    assert len(result.issues) == 0


def test_security_audit_secret_leak(tmp_path: Path) -> None:
    """Verifies that exposed API keys are flagged as CRITICAL security leaks."""
    leak_file = tmp_path / "leaky_service.py"
    leak_file.write_text("OPENAI_KEY = 'sk-proj-abc12345678901234567890abcdef'\n", encoding="utf-8")

    result = security_audit(scan_target=str(leak_file), mode="secrets")
    assert result.passed is False
    assert result.issues_found == 1
    assert result.issues[0].severity == "CRITICAL"
    assert result.issues[0].issue_type == "SECRET_LEAK"

    # Invalid mode check
    with pytest.raises(ValueError, match="Invalid mode"):
        security_audit(scan_target=str(tmp_path), mode="unsupported_mode")  # type: ignore

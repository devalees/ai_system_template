"""
Golden Benchmark Evaluation Suite for Sovereign Autonomous Agents.

Executes deterministic multi-role scenarios across the 5 Department Heads:
1. Orchestrator (DAG planning, pre-flight memory injection, circular dependency guard)
2. Cost Controller (Spend velocity milestones, model efficiency advisory)
3. QA Auditor (Tiered risk-based deliverable evaluation, deliverable hygiene)
4. Comms Agent (Zero-trust client queries, deliverable inventory, notifications)
5. Security Guard (Secret leak interception, cryptographic key detection, RBAC boundaries)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from agent_service.mcp.schemas import (
    BudgetStatusResult,
    ClientActionResult,
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
from agent_service.qa.pipeline import QAPipeline
from agent_service.telemetry.tracer import TelemetryTracer, compute_token_cost


# ---------------------------------------------------------------------------
# Role 1: Orchestrator Scenarios
# ---------------------------------------------------------------------------

def test_scenario_orchestrator_preflight_memory_injection(tmp_path: Path) -> None:
    """Scenario 1.1: Orchestrator recalls past solution and injects into DAG turn 1."""
    db_file = tmp_path / "memory.db"
    store = MemoryStore(db_path=db_file)
    store.add_memory(
        title="Migrate SQLite to PostgreSQL",
        content="Export tables using pgloader with schema type mapping.",
        category="database",
        scope="generalized",
    )
    store.close()

    # Query matching memory
    store_check = MemoryStore(db_path=db_file)
    recalled = store_check.recall_similar("Migrate database from SQLite to PostgreSQL", top_k=2)
    assert len(recalled) == 1
    assert "pgloader" in recalled[0]["content"]
    store_check.close()


def test_scenario_orchestrator_multi_specialist_dag() -> None:
    """Scenario 1.2: Orchestrator generates valid topologically ordered 4-specialist DAG."""
    dag = decompose_task_dag("Implement OAuth2 authentication microservice")
    assert isinstance(dag, TaskDAGResult)
    assert dag.total_tasks == 4

    # Verify order: orchestrator -> cost_controller -> security_guard -> qa_auditor
    expected_flow = ["orchestrator", "cost_controller", "security_guard", "qa_auditor"]
    actual_flow = [t.assigned_to for t in dag.tasks]
    assert actual_flow == expected_flow


def test_scenario_orchestrator_circular_dag_rejection() -> None:
    """Scenario 1.3: Orchestrator strictly rejects circular task dependencies."""
    invalid_tasks = [
        {"id": "a", "title": "Task A", "assigned_to": "orchestrator", "dependencies": ["b"], "description": "a"},
        {"id": "b", "title": "Task B", "assigned_to": "cost_controller", "dependencies": ["a"], "description": "b"},
    ]
    with pytest.raises(ValueError):
        decompose_task_dag("Circular test", context={"tasks": [
            {"id": "a", "title": "A", "assigned_to": "orchestrator", "dependencies": ["a"], "description": "self"}
        ]})


# ---------------------------------------------------------------------------
# Role 2: Cost Controller Scenarios
# ---------------------------------------------------------------------------

def test_scenario_cost_controller_burn_progression() -> None:
    """Scenario 2.1: Cost Controller correctly triggers milestone transitions as spend grows."""
    daily_cap = 20.0

    # 1. 20% spend -> HEALTHY
    s1 = audit_token_budget(daily_cap_usd=daily_cap, current_spend_usd=4.0)
    assert s1.status == "HEALTHY"

    # 2. 60% spend -> VELOCITY_WARNING
    s2 = audit_token_budget(daily_cap_usd=daily_cap, current_spend_usd=12.0)
    assert s2.status == "VELOCITY_WARNING"

    # 3. 85% spend -> CRITICAL
    s3 = audit_token_budget(daily_cap_usd=daily_cap, current_spend_usd=17.0)
    assert s3.status == "CRITICAL"

    # 4. 100% spend -> EXCEEDED
    s4 = audit_token_budget(daily_cap_usd=daily_cap, current_spend_usd=20.5)
    assert s4.status == "EXCEEDED"


def test_scenario_cost_controller_multi_turn_telemetry(tmp_path: Path) -> None:
    """Scenario 2.2: Tracer records multi-turn generation costs accurately."""
    tracer = TelemetryTracer(
        profile_name="cost_controller",
        objective="Calculate multi-turn token costs",
        traces_dir=tmp_path,
    )

    tracer.record_generation(
        prompt="Turn 1 prompt",
        output="Turn 1 completion",
        prompt_tokens=1000,
        completion_tokens=200,
        model="anthropic/claude-3.5-sonnet",
    )
    tracer.record_generation(
        prompt="Turn 2 prompt",
        output="Turn 2 completion",
        prompt_tokens=1500,
        completion_tokens=300,
        model="anthropic/claude-3.5-sonnet",
    )

    metrics = tracer.get_metrics()
    assert metrics["total_prompt_tokens"] == 2500
    assert metrics["total_completion_tokens"] == 500
    expected_cost = round((2.5 * 0.003) + (0.5 * 0.015), 6)
    assert metrics["total_cost_usd"] == expected_cost


# ---------------------------------------------------------------------------
# Role 3: QA Auditor Scenarios
# ---------------------------------------------------------------------------

def test_scenario_qa_auditor_zero_token_direct_pass() -> None:
    """Scenario 3.1: Valid, clean, standard code passes Tier 1 with $0 token spend."""
    code = """
def format_currency(amount: float, symbol: str = "$") -> str:
    \"\"\"Formats a float into currency string representation.\"\"\"
    return f"{symbol}{amount:,.2f}"
"""
    qa = QAPipeline()
    result = qa.evaluate(code_content=code, risk_level="low", confidence_score=0.95)
    assert result.verdict == "approved"
    assert result.tier_invoked == 1
    assert result.requires_tier_3_review is False


def test_scenario_qa_auditor_syntax_traceback_generation() -> None:
    """Scenario 3.2: Malformed Python code produces actionable line-specific self-correction prompt."""
    bad_code = "for i in range(10)\n    print(i)\n"
    qa = QAPipeline()
    result = qa.evaluate(code_content=bad_code)
    assert result.verdict == "rejected"
    assert result.tier_invoked == 2
    assert "SyntaxError at line 1" in result.self_correction_prompt


def test_scenario_qa_auditor_security_risk_escalation() -> None:
    """Scenario 3.3: Deliverable with critical architectural impact triggers Tier 3 deep review."""
    critical_code = """
def delete_tenant_cluster(tenant_id: str) -> bool:
    \"\"\"Purges all persistent volumes and databases for a tenant.\"\"\"
    return cluster_manager.destroy(tenant_id)
"""
    qa = QAPipeline()
    result = qa.evaluate(code_content=critical_code, risk_level="critical", confidence_score=0.99)
    assert result.verdict == "escalate_tier_3"
    assert result.tier_invoked == 3
    assert result.requires_tier_3_review is True


# ---------------------------------------------------------------------------
# Role 4: Comms Agent Scenarios
# ---------------------------------------------------------------------------

def test_scenario_comms_agent_status_and_inventory() -> None:
    """Scenario 4.1: Comms Agent queries operational status and deliverable catalog."""
    status_res = client_service_action("query_status")
    assert status_res.success is True
    assert status_res.data["system_status"] == "operational"

    catalog_res = client_service_action("get_deliverables")
    assert catalog_res.success is True
    assert "deliverables" in catalog_res.data


def test_scenario_comms_agent_notification_dispatch() -> None:
    """Scenario 4.2: Comms Agent formats and verifies delivery notice."""
    notice = client_service_action(
        "dispatch_notification",
        {"recipient": "client_enterprise", "message": "Cluster deployment completed successfully."},
    )
    assert notice.success is True
    assert notice.data["recipient"] == "client_enterprise"
    assert "Cluster deployment completed" in notice.message


# ---------------------------------------------------------------------------
# Role 5: Security Guard Scenarios
# ---------------------------------------------------------------------------

def test_scenario_security_guard_secret_interception(tmp_path: Path) -> None:
    """Scenario 5.1: Security Guard intercepts hardcoded API tokens in source files."""
    dirty_file = tmp_path / "config_leaked.py"
    dirty_file.write_text(
        "ANTHROPIC_KEY = 'sk-ant-1234567890abcdef1234567890abcdef1234567890'\n",
        encoding="utf-8",
    )

    audit = security_audit(scan_target=str(dirty_file), mode="secrets")
    assert audit.passed is False
    assert audit.issues_found >= 1
    assert audit.issues[0].severity == "CRITICAL"
    assert audit.issues[0].issue_type == "SECRET_LEAK"


def test_scenario_security_guard_private_key_interception(tmp_path: Path) -> None:
    """Scenario 5.2: Security Guard flags hardcoded RSA private keys."""
    key_file = tmp_path / "server.key"
    key_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )

    audit = security_audit(scan_target=str(key_file), mode="secrets")
    assert audit.passed is False
    assert any(i.issue_type == "SECRET_LEAK" for i in audit.issues)


def test_scenario_security_guard_clean_codebase_approval(tmp_path: Path) -> None:
    """Scenario 5.3: Security Guard signs off cleanly on compliant repositories."""
    clean_dir = tmp_path / "secure_app"
    clean_dir.mkdir()
    (clean_dir / "app.py").write_text("import os\nSECRET = os.getenv('APP_SECRET')\n", encoding="utf-8")

    audit = security_audit(scan_target=str(clean_dir), mode="secrets")
    assert audit.passed is True
    assert audit.issues_found == 0

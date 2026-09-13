"""
Unit Test Suite for Modular FastMCP Servers & Zero-Trust Profile Scoping.

Validates:
- Standalone execution and contracts for all 6 modular FastMCP servers:
  1. common_server (semantic_memory_recall, get_platform_status)
  2. orchestrator_server (decompose_task_dag)
  3. qa_server (validate_code_deliverable)
  4. security_server (security_audit)
  5. cost_server (audit_token_budget)
  6. comms_server (client_service_action)
- Zero-trust profile scoping and toolset mutual exclusivity.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from agent_service.mcp.common_server import get_platform_status, semantic_memory_recall
from agent_service.mcp.comms_server import client_service_action
from agent_service.mcp.cost_server import audit_token_budget
from agent_service.mcp.orchestrator_server import decompose_task_dag
from agent_service.mcp.qa_server import validate_code_deliverable
from agent_service.mcp.schemas import (
    BudgetStatusResult,
    ClientActionResult,
    MemoryRecallResult,
    PlatformStatusResult,
    SecurityAuditResult,
    TaskDAGResult,
    ValidationResult,
)
from agent_service.mcp.security_server import security_audit
from agent_service.memory.vector_store import MemoryStore


def test_common_server_semantic_memory_recall(tmp_path: Path) -> None:
    """Verifies that common_server executes semantic recall on sqlite-vec."""
    # Seed a memory in vector store
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path=db_path)
    store.add_memory(
        title="Raft Distributed Consensus",
        content="Distributed consensus achieved via Raft algorithm in cluster nodes.",
        category="architecture",
        scope="generalized",
        metadata={"tags": ["consensus", "raft"]},
    )

    # Call semantic recall directly
    results = store.recall_similar(query_text="How do cluster nodes reach agreement?", top_k=3, threshold=0.1)
    assert len(results) >= 1
    assert "consensus" in results[0]["metadata"]["tags"]
    store.close()

    # Verify MCP tool wrapper contract
    res = semantic_memory_recall("consensus Raft algorithm", limit=2)
    assert isinstance(res, MemoryRecallResult)
    assert res.query == "consensus Raft algorithm"


def test_common_server_platform_status() -> None:
    """Verifies platform health, uptime, and active service inventory."""
    status = get_platform_status()
    assert isinstance(status, PlatformStatusResult)
    assert status.status == "OPERATIONAL"
    assert status.version == "2.0.0-sovereign"
    assert status.uptime_seconds >= 0.0
    assert "sqlite-vec-memory-engine" in status.active_services
    assert "modular-fastmcp-toolsets" in status.active_services
    assert status.total_memories >= 0


def test_orchestrator_server_dag_decomposition() -> None:
    """Verifies orchestrator DAG planner tool."""
    dag = decompose_task_dag("Scale payment processing pipeline")
    assert isinstance(dag, TaskDAGResult)
    assert dag.total_tasks == 4
    assert dag.tasks[0].assigned_to == "orchestrator"
    assert dag.tasks[1].assigned_to == "cost_controller"


def test_qa_server_validation() -> None:
    """Verifies QA deliverable validation tool."""
    clean_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    res = validate_code_deliverable(code_content=clean_code)
    assert isinstance(res, ValidationResult)
    assert res.is_valid is True
    assert res.syntax_ok is True
    assert res.verdict == "approved"

    broken_code = "def invalid(\n"
    res_err = validate_code_deliverable(code_content=broken_code)
    assert res_err.is_valid is False
    assert res_err.syntax_ok is False
    assert res_err.verdict == "rejected"
    assert any("SyntaxError" in err for err in res_err.errors)


def test_security_server_audit(tmp_path: Path) -> None:
    """Verifies SecOps threat and credential scanner tool."""
    secret_file = tmp_path / "leaked_config.py"
    secret_file.write_text("OPENAI_KEY = 'sk-1234567890abcdef1234567890abcdef'\n")

    res = security_audit(scan_target=str(secret_file), mode="secrets")
    assert isinstance(res, SecurityAuditResult)
    assert res.passed is False
    assert res.issues_found >= 1
    assert any(i.issue_type == "SECRET_LEAK" for i in res.issues)


def test_cost_server_audit() -> None:
    """Verifies financial controller budget audit tool."""
    res = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=2.50)
    assert isinstance(res, BudgetStatusResult)
    assert res.status == "HEALTHY"
    assert res.burn_rate_pct == 25.0

    res_warn = audit_token_budget(daily_cap_usd=10.0, current_spend_usd=6.00)
    assert res_warn.status == "VELOCITY_WARNING"


def test_comms_server_action() -> None:
    """Verifies client communications concierge action tool."""
    res = client_service_action("query_status")
    assert isinstance(res, ClientActionResult)
    assert res.success is True
    assert res.data["system_status"] == "operational"

    res_notif = client_service_action("dispatch_notification", {"recipient": "stakeholder", "message": "Phase 37 ready"})
    assert res_notif.success is True
    assert res_notif.data["dispatched"] is True


def test_profile_scoping_isolation() -> None:
    """Verifies least-privilege scoping across all 5 profile YAML declarations."""
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"

    expected_toolsets = {
        "comms_agent": {"common_tools", "comms_tools", "integration_tools", "file_ops"},
        "cost_controller": {"common_tools", "cost_tools", "file_ops"},
        "orchestrator": {"common_tools", "orchestrator_tools", "integration_tools", "kanban", "delegate", "file_ops"},
        "qa_auditor": {"common_tools", "qa_tools", "file_ops", "terminal"},
        "security_guard": {"common_tools", "security_tools", "file_ops", "terminal"},
    }

    for prof_name, expected in expected_toolsets.items():
        prof_yaml = profiles_dir / prof_name / "profile.yaml"
        assert prof_yaml.exists(), f"Profile {prof_name} missing profile.yaml"
        data = yaml.safe_load(prof_yaml.read_text())
        actual = set(data.get("toolsets", []))
        assert actual == expected, f"Profile {prof_name} toolsets mismatch: {actual} != {expected}"

    # Verify mutual exclusivity of specialist domain tools
    comms_tools = expected_toolsets["comms_agent"]
    qa_tools = expected_toolsets["qa_auditor"]
    sec_tools = expected_toolsets["security_guard"]
    cost_tools = expected_toolsets["cost_controller"]

    assert "qa_tools" not in comms_tools
    assert "security_tools" not in comms_tools
    assert "comms_tools" not in qa_tools
    assert "qa_tools" not in sec_tools
    assert "integration_tools" not in qa_tools
    assert "integration_tools" not in sec_tools
    assert "integration_tools" not in cost_tools


"""
Unit Test Suite for Glass-Box Observability and Telemetry (Langfuse Tracer).

Validates:
- Precise token cost calculation across models.
- Turn-by-turn prompt and thinking stream span recording.
- FastMCP tool execution timing and output serialization.
- Resilient local JSON persistence and aggregate metric calculation.
- Langfuse non-blocking ingestion lifecycle.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_service.telemetry.tracer import (
    TelemetryTracer,
    compute_token_cost,
)


def test_compute_token_cost() -> None:
    """Verifies token pricing catalog calculations across supported models."""
    # 1,000 prompt + 1,000 completion on Claude 3.5 Sonnet
    cost_claude = compute_token_cost(1000, 1000, "anthropic/claude-3.5-sonnet")
    assert cost_claude == 0.018  # 0.003 + 0.015

    # 10,000 prompt + 2,000 completion on Gemini Flash
    cost_gemini = compute_token_cost(10000, 2000, "google/gemini-2.5-flash")
    assert cost_gemini == round(10 * 0.000075 + 2 * 0.0003, 6)

    # 4,000 prompt + 1,000 completion on GPT-4o
    cost_gpt4o = compute_token_cost(4000, 1000, "openai/gpt-4o")
    assert cost_gpt4o == round(4 * 0.0025 + 1 * 0.010, 6)


def test_tracer_generation_recording(tmp_path: Path) -> None:
    """Verifies generation span tracking and token accumulation."""
    tracer = TelemetryTracer(
        profile_name="orchestrator",
        objective="Decompose infrastructure task",
        traces_dir=tmp_path,
    )

    gen1 = tracer.record_generation(
        prompt="Analyze objective and plan next steps",
        output="Decomposition completed: 4 sub-tasks created.",
        prompt_tokens=450,
        completion_tokens=120,
        model="anthropic/claude-3.5-sonnet",
        thinking="Evaluating dependencies and past memory solutions...",
        duration_ms=450.0,
    )

    assert gen1.prompt_tokens == 450
    assert gen1.completion_tokens == 120
    assert gen1.cost_usd > 0.0
    assert gen1.thinking is not None
    assert len(tracer.generations) == 1

    metrics = tracer.get_metrics()
    assert metrics["total_tokens"] == 570
    assert metrics["total_prompt_tokens"] == 450
    assert metrics["total_completion_tokens"] == 120
    assert metrics["total_cost_usd"] == gen1.cost_usd


def test_tracer_tool_call_recording(tmp_path: Path) -> None:
    """Verifies MCP tool call recording and output serialization."""
    tracer = TelemetryTracer(
        profile_name="qa_auditor",
        objective="Verify code syntax",
        traces_dir=tmp_path,
    )

    tc = tracer.record_tool_call(
        tool_name="validate_code_deliverable",
        arguments={"target_file": "service.py"},
        result={"verdict": "approved", "is_valid": True},
        status="success",
        duration_ms=4.2,
    )

    assert tc.tool_name == "validate_code_deliverable"
    assert tc.result["verdict"] == "approved"
    assert tc.duration_ms == 4.2
    assert len(tracer.tool_calls) == 1


def test_tracer_end_task_and_local_persistence(tmp_path: Path) -> None:
    """Verifies that concluding a task produces complete metrics and saves local JSON trace."""
    tracer = TelemetryTracer(
        task_id="test-task-12345",
        profile_name="cost_controller",
        objective="Audit token spend",
        traces_dir=tmp_path,
    )

    tracer.record_generation(
        prompt="Audit spend",
        output="Budget is healthy at 25%",
        prompt_tokens=200,
        completion_tokens=50,
    )
    tracer.record_tool_call(
        tool_name="audit_token_budget",
        arguments={"daily_cap_usd": 10.0, "current_spend_usd": 2.5},
        result={"status": "HEALTHY"},
        duration_ms=1.5,
    )

    summary = tracer.end_task(status="completed")

    assert summary["task_id"] == "test-task-12345"
    assert summary["status"] == "completed"
    assert summary["metrics"]["total_tokens"] == 250
    assert summary["metrics"]["generation_count"] == 1
    assert summary["metrics"]["tool_call_count"] == 1

    # Verify JSON file on disk
    trace_file = tmp_path / "test-task-12345.json"
    assert trace_file.exists()

    data = json.loads(trace_file.read_text(encoding="utf-8"))
    assert data["task_id"] == "test-task-12345"
    assert len(data["generations"]) == 1
    assert len(data["tool_calls"]) == 1


def test_tracer_langfuse_non_blocking_dispatch(tmp_path: Path) -> None:
    """Verifies that Langfuse HTTP dispatch runs gracefully and does not throw errors even if offline."""
    tracer = TelemetryTracer(
        profile_name="security_guard",
        objective="Threat audit",
        host="http://localhost:3100",  # Live Langfuse host
        traces_dir=tmp_path,
    )

    tracer.record_generation(
        prompt="Scan repository for leaked keys",
        output="Zero critical leaks found.",
        prompt_tokens=100,
        completion_tokens=20,
    )

    # Conclude task; should dispatch to Langfuse without exceptions
    summary = tracer.end_task(status="completed")
    assert summary["status"] == "completed"

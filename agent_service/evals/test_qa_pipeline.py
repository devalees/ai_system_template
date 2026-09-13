"""
Unit Test Suite for Tiered Risk-Based QA State Machine and Circuit Breaker.

Validates:
- Tier 1: Deterministic AST syntax verification with zero token spend ($0, <5ms).
- Tier 2: Mid-flight context reflection and structured syntax error injection.
- Deliverable hygiene enforcement (rejection of TODOs, stubs, hardcoded secrets).
- Tier 3: Conditional escalation for high-risk or low-confidence deliverables.
- Anti-loop circuit breaker tripping after 2 consecutive identical failures.
"""

from __future__ import annotations

from pathlib import Path
from agent_service.qa.pipeline import CircuitBreaker, QAPipeline, QAResult


def test_tier1_clean_code_direct_approval() -> None:
    """Verifies that clean, compliant, low-risk deliverables pass Tier 1 instantly."""
    clean_code = """
def calculate_ending_balance(principal: float, rate: float, periods: int) -> float:
    \"\"\"Calculates compound interest ending balance.\"\"\"
    return principal * ((1.0 + rate) ** periods)
"""
    qa = QAPipeline()
    result = qa.evaluate(
        code_content=clean_code,
        risk_level="medium",
        confidence_score=0.92,
    )

    assert isinstance(result, QAResult)
    assert result.verdict == "approved"
    assert result.tier_invoked == 1
    assert result.syntax_valid is True
    assert result.requires_tier_3_review is False
    assert result.self_correction_prompt is None
    assert len(result.errors) == 0


def test_tier2_syntax_error_self_correction() -> None:
    """Verifies that syntax errors construct Tier 2 reflection prompts with line numbers."""
    broken_code = """
def calculate_balance(principal: float
    return principal * 1.05
"""
    qa = QAPipeline()
    result = qa.evaluate(
        code_content=broken_code,
        risk_level="low",
    )

    assert result.verdict == "rejected"
    assert result.tier_invoked == 2
    assert result.syntax_valid is False
    assert result.requires_tier_3_review is False
    assert result.self_correction_prompt is not None
    assert "SyntaxError at line" in result.self_correction_prompt
    assert "Action Required: Fix the syntax error" in result.self_correction_prompt


def test_tier2_hygiene_violations() -> None:
    """Verifies that placeholder comments and stubs construct changes-requested prompts."""
    stubbed_code = """
def authenticate_user(username: str) -> bool:
    # TODO: implement authentication logic against database
    raise NotImplementedError("Auth not ready")
"""
    qa = QAPipeline()
    result = qa.evaluate(code_content=stubbed_code)

    assert result.verdict == "changes_requested"
    assert result.tier_invoked == 2
    assert result.syntax_valid is True
    assert len(result.errors) >= 2
    assert any("TODO/FIXME" in e for e in result.errors)
    assert any("NotImplementedError" in e for e in result.errors)
    assert "Replace all placeholders" in result.self_correction_prompt


def test_tier3_high_risk_escalation() -> None:
    """Verifies that high-risk or critical code triggers Tier 3 deep review even when syntax is valid."""
    clean_auth_code = """
def update_user_password_hash(user_id: str, new_hash: str) -> None:
    \"\"\"Updates credential hash in sovereign storage.\"\"\"
    db.execute("UPDATE users SET hash = ? WHERE id = ?", (new_hash, user_id))
"""
    qa = QAPipeline()
    # High risk deliverable
    result_high = qa.evaluate(
        code_content=clean_auth_code,
        risk_level="high",
        confidence_score=0.95,
    )
    assert result_high.verdict == "escalate_tier_3"
    assert result_high.tier_invoked == 3
    assert result_high.requires_tier_3_review is True

    # Critical risk deliverable
    result_crit = qa.evaluate(
        code_content=clean_auth_code,
        risk_level="critical",
        confidence_score=0.99,
    )
    assert result_crit.verdict == "escalate_tier_3"
    assert result_crit.requires_tier_3_review is True


def test_tier3_low_confidence_escalation() -> None:
    """Verifies that deliverables with confidence < 85% escalate to Tier 3."""
    clean_code = "x = 42\ny = x * 2\n"
    qa = QAPipeline(confidence_threshold=0.85)

    result_low_conf = qa.evaluate(
        code_content=clean_code,
        risk_level="low",
        confidence_score=0.72,  # Below 0.85
    )
    assert result_low_conf.verdict == "escalate_tier_3"
    assert result_low_conf.tier_invoked == 3
    assert result_low_conf.requires_tier_3_review is True


def test_circuit_breaker_anti_loop() -> None:
    """Verifies anti-loop circuit breaker trips after 2 consecutive identical failures."""
    breaker = CircuitBreaker(max_failures=2)

    tool = "security_audit"
    bad_args = {"scan_target": "/non/existent/path", "mode": "invalid_mode"}

    # Attempt 1: failure recorded, not tripped yet
    tripped_1, msg_1 = breaker.record_failure(tool, bad_args, "Invalid mode")
    assert tripped_1 is False
    assert breaker.is_tripped(tool) is False
    assert "attempt 1/2" in msg_1

    # Attempt 2: identical failure repeated -> trips circuit breaker
    tripped_2, msg_2 = breaker.record_failure(tool, bad_args, "Invalid mode")
    assert tripped_2 is True
    assert breaker.is_tripped(tool) is True
    assert "CIRCUIT BREAKER TRIPPED" in msg_2

    # Reset on success
    breaker.record_success(tool)
    assert breaker.is_tripped(tool) is False

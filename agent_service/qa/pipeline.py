"""
Tiered Risk-Based Quality Assurance State Machine and Anti-Loop Circuit Breaker.

Enforces:
1. Tier 1: Deterministic in-process Python AST parsing & hygiene checks ($0, <5ms).
2. Tier 2: Mid-flight context reflection generating structured correction prompts.
3. Tier 3: Conditional escalation to high-reasoning review only when risk is high or confidence < 85%.
4. Anti-loop circuit breaker terminating repeated identical tool failures (limit: 2).
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("agent_service.qa")

# Deliverable hygiene violation patterns
HYGIENE_PATTERNS = [
    (r"(?i)#\s*(?:TODO|FIXME)\b", "Unresolved placeholder comment (TODO/FIXME)"),
    (r"\braise\s+NotImplementedError\b", "Stubbed unimplemented code (NotImplementedError)"),
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "Hardcoded API Secret"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Hardcoded Bearer Token"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "Hardcoded Private Cryptographic Key"),
]


class QAResult(BaseModel):
    """Output contract for QA deliverable evaluation."""
    target: str = Field(..., description="Target file or deliverable identifier")
    tier_invoked: Literal[1, 2, 3] = Field(..., description="Highest QA tier invoked")
    verdict: Literal["approved", "changes_requested", "rejected", "escalate_tier_3"] = Field(
        ..., description="Final QA verdict"
    )
    syntax_valid: bool = Field(..., description="True if code passed AST compilation cleanly")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence rating (0.0 to 1.0)")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Risk category")
    errors: List[str] = Field(default_factory=list, description="Diagnostic error descriptions")
    self_correction_prompt: Optional[str] = Field(
        default=None, description="Formatted error injection for mid-flight self-correction"
    )
    requires_tier_3_review: bool = Field(
        default=False, description="Whether deliverable requires deep LLM review"
    )


class CircuitBreaker:
    """
    Anti-loop circuit breaker that prevents agents from repeating the same
    failed tool invocations in an infinite loop.
    """

    MAX_CONSECUTIVE_FAILURES: int = 2

    def __init__(self, max_failures: int = MAX_CONSECUTIVE_FAILURES) -> None:
        """
        Initializes the circuit breaker.

        Args:
            max_failures: Max permitted identical consecutive failures before tripping.
        """
        self.max_failures = max_failures
        self._failure_counts: Dict[str, int] = {}
        self._last_signatures: Dict[str, str] = {}
        self._is_tripped: Dict[str, bool] = {}

    def _compute_call_signature(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Computes a deterministic hash of tool name and input arguments."""
        serialized = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def record_failure(
        self,
        tool_name: str,
        args: Dict[str, Any],
        error_message: str,
    ) -> Tuple[bool, str]:
        """
        Records a failed tool execution and evaluates circuit breaker status.

        Args:
            tool_name: Name of tool that failed.
            args: Input arguments passed to the tool.
            error_message: Error string returned by tool.

        Returns:
            Tuple[bool, str]: (is_tripped, diagnostic_message)
        """
        sig = self._compute_call_signature(tool_name, args)
        last_sig = self._last_signatures.get(tool_name)

        if last_sig == sig:
            self._failure_counts[tool_name] = self._failure_counts.get(tool_name, 0) + 1
        else:
            self._failure_counts[tool_name] = 1
            self._last_signatures[tool_name] = sig

        count = self._failure_counts[tool_name]

        if count >= self.max_failures:
            self._is_tripped[tool_name] = True
            msg = (
                f"CIRCUIT BREAKER TRIPPED for tool '{tool_name}'. Repeated identical failure "
                f"{count} times consecutively. Execution aborted: {error_message}"
            )
            logger.error(msg)
            return True, msg

        msg = (
            f"Tool '{tool_name}' failed attempt {count}/{self.max_failures}. "
            f"Mid-flight retry permitted: {error_message}"
        )
        return False, msg

    def record_success(self, tool_name: str) -> None:
        """
        Resets the circuit breaker failure count upon successful execution.

        Args:
            tool_name: Tool that succeeded.
        """
        self._failure_counts[tool_name] = 0
        self._last_signatures.pop(tool_name, None)
        self._is_tripped[tool_name] = False

    def is_tripped(self, tool_name: str) -> bool:
        """Returns True if the circuit breaker is actively tripped for the given tool."""
        return self._is_tripped.get(tool_name, False)


class QAPipeline:
    """
    Quality Assurance Evaluation Pipeline enforcing the 3-tier state machine:
    Tier 1: In-process AST check ($0, <5ms).
    Tier 2: Mid-flight traceback injection for instant self-correction.
    Tier 3: Conditional high-reasoning review reserved for high-risk changes.
    """

    CONFIDENCE_THRESHOLD: float = 0.85

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD) -> None:
        """
        Initializes the QA Pipeline.

        Args:
            confidence_threshold: Minimum confidence score required to bypass Tier 3.
        """
        self.confidence_threshold = confidence_threshold
        self.circuit_breaker = CircuitBreaker()

    def evaluate(
        self,
        code_content: Optional[str] = None,
        target_file: Optional[str] = None,
        risk_level: Literal["low", "medium", "high", "critical"] = "medium",
        confidence_score: float = 0.90,
    ) -> QAResult:
        """
        Evaluates deliverable against the 3-tier risk-based state machine.

        Args:
            code_content: Raw code string to validate.
            target_file: Path to deliverable file if code_content is omitted.
            risk_level: Assessed risk classification ('low', 'medium', 'high', 'critical').
            confidence_score: Specialist confidence rating (0.0 to 1.0).

        Returns:
            QAResult: Structured evaluation verdict, tier invoked, and self-correction prompt.
        """
        target_name = target_file or "<inline_code>"
        raw_code = code_content

        if raw_code is None and target_file:
            path = Path(target_file)
            if not path.exists():
                return QAResult(
                    target=target_name,
                    tier_invoked=1,
                    verdict="rejected",
                    syntax_valid=False,
                    confidence_score=0.0,
                    risk_level=risk_level,
                    errors=[f"Target file '{target_file}' not found."],
                    self_correction_prompt=f"Target deliverable '{target_file}' does not exist on disk. Please create or verify the file path.",
                    requires_tier_3_review=False,
                )
            raw_code = path.read_text(encoding="utf-8", errors="ignore")

        if not raw_code:
            return QAResult(
                target=target_name,
                tier_invoked=1,
                verdict="rejected",
                syntax_valid=False,
                confidence_score=0.0,
                risk_level=risk_level,
                errors=["Empty deliverable code content."],
                self_correction_prompt="Empty code deliverable provided. Please supply executable implementation code.",
                requires_tier_3_review=False,
            )

        # -------------------------------------------------------------------
        # Tier 1: Deterministic Python AST Compilation Check
        # -------------------------------------------------------------------
        try:
            ast.parse(raw_code, filename=target_name)
        except SyntaxError as exc:
            # Syntax failure -> Construct Tier 2 mid-flight self-correction injection
            syntax_err = f"SyntaxError at line {exc.lineno}, col {exc.offset}: {exc.msg}"
            correction_prompt = (
                f"Error: Deliverable '{target_name}' failed Tier 1 AST syntax verification.\n"
                f"Traceback: {syntax_err}\n"
                f"Action Required: Fix the syntax error at line {exc.lineno} and resubmit."
            )
            return QAResult(
                target=target_name,
                tier_invoked=2,
                verdict="rejected",
                syntax_valid=False,
                confidence_score=0.0,
                risk_level=risk_level,
                errors=[syntax_err],
                self_correction_prompt=correction_prompt,
                requires_tier_3_review=False,
            )

        # -------------------------------------------------------------------
        # Deliverable Hygiene & Security Leak Verification
        # -------------------------------------------------------------------
        hygiene_violations: List[str] = []
        for pattern, desc in HYGIENE_PATTERNS:
            matches = re.findall(pattern, raw_code)
            if matches:
                hygiene_violations.append(f"{desc} ({len(matches)} instance(s))")

        if hygiene_violations:
            correction_prompt = (
                f"Error: Deliverable '{target_name}' contains hygiene violations:\n"
                + "\n".join(f"- {v}" for v in hygiene_violations)
                + "\nAction Required: Replace all placeholders or remove hardcoded secrets."
            )
            return QAResult(
                target=target_name,
                tier_invoked=2,
                verdict="changes_requested",
                syntax_valid=True,
                confidence_score=confidence_score,
                risk_level=risk_level,
                errors=hygiene_violations,
                self_correction_prompt=correction_prompt,
                requires_tier_3_review=False,
            )

        # -------------------------------------------------------------------
        # Tier 3: Risk & Confidence Gate
        # -------------------------------------------------------------------
        # High/critical risk deliverables OR low-confidence outputs require deep LLM review
        if risk_level in ("high", "critical") or confidence_score < self.confidence_threshold:
            reasons = []
            if risk_level in ("high", "critical"):
                reasons.append(f"Risk level '{risk_level}' requires authoritative review")
            if confidence_score < self.confidence_threshold:
                reasons.append(f"Confidence {confidence_score:.2f} is below threshold {self.confidence_threshold:.2f}")

            return QAResult(
                target=target_name,
                tier_invoked=3,
                verdict="escalate_tier_3",
                syntax_valid=True,
                confidence_score=confidence_score,
                risk_level=risk_level,
                errors=[],
                self_correction_prompt=None,
                requires_tier_3_review=True,
            )

        # -------------------------------------------------------------------
        # Tier 1 Direct Approval ($0 token cost, sub-5ms)
        # -------------------------------------------------------------------
        return QAResult(
            target=target_name,
            tier_invoked=1,
            verdict="approved",
            syntax_valid=True,
            confidence_score=confidence_score,
            risk_level=risk_level,
            errors=[],
            self_correction_prompt=None,
            requires_tier_3_review=False,
        )

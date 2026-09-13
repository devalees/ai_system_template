"""
Tiered Risk-Based Quality Assurance and Self-Correction Package.

Provides 3-tier validation state machine:
- Tier 1: Deterministic in-process AST syntax checking ($0, <5ms).
- Tier 2: Mid-flight context reflection and structured error injection.
- Tier 3: Conditional high-reasoning review for high-risk / low-confidence deliverables.
- Anti-loop circuit breaker preventing repetitive failed tool attempts.
"""

from .pipeline import CircuitBreaker, QAPipeline, QAResult

__all__ = ["QAPipeline", "QAResult", "CircuitBreaker"]

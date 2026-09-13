"""
FastMCP QA Tools Server.

Exposes specialized validation and code quality auditing tools for the QA Gatekeeper (qa_auditor).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import List, Optional

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import ValidationResult

qa_mcp = FastMCP("SovereignQATools")

FORBIDDEN_CODE_PATTERNS = [
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "Hardcoded OpenAI / API secret detected"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Hardcoded Bearer authorization token detected"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "Hardcoded Private Key detected"),
    (r"(?i)#\s*(TODO|FIXME)\b", "Unfinished placeholder comment (TODO/FIXME) detected"),
    (r"\braise\s+NotImplementedError\b", "Stubbed placeholder NotImplementedError detected"),
]


@qa_mcp.tool(
    name="validate_code_deliverable",
    description="Performs Tier 1 deterministic AST syntax verification and hygiene auditing on code.",
)
def validate_code_deliverable(
    code_content: Optional[str] = None,
    target_file: Optional[str] = None,
    schema_type: str = "python",
) -> ValidationResult:
    """
    Performs Tier 1 deterministic AST syntax verification and hygiene auditing on code.

    Guarantees zero-cost, sub-5ms deterministic syntax checking. If syntax fails,
    provides exact line numbers and syntax error messages for Tier 2 in-flight self-correction.
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
            verdict="rejected",
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


if __name__ == "__main__":
    qa_mcp.run(transport="stdio", show_banner=False)

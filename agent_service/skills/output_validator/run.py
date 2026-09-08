#!/usr/bin/env python3
"""
Output Validator Skill Runner.

Empirical verification engine used by `qa_auditor` to audit code, schemas,
and documentation prior to signing off on Kanban deliverables.
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

# Patterns for sensitive leaks and placeholders
LEAK_PATTERNS = [
    (re.compile(r'(?:sk-[a-zA-Z0-9_-]{20,})', re.IGNORECASE), "Exposed OpenAI / OpenRouter Secret Key"),
    (re.compile(r'(?:gsk_[a-zA-Z0-9_-]{20,})', re.IGNORECASE), "Exposed Groq API Key"),
    (re.compile(r'(?:ghp_[a-zA-Z0-9]{36})', re.IGNORECASE), "Exposed GitHub Personal Access Token"),
    (re.compile(r'-----BEGIN\s+(?:RSA|OPENSSH|EC|DSA)?\s*PRIVATE KEY-----'), "Exposed Private Key"),
    (re.compile(r'password\s*[:=]\s*["\']([^"\']{6,})["\']', re.IGNORECASE), "Hardcoded Password String"),
]

PLACEHOLDER_PATTERNS = [
    (re.compile(r'\b(?:TODO|FIXME|XXX|HACK|CHANGEME)\b', re.IGNORECASE), "Unfinished Task Placeholder"),
    (re.compile(r'raise\s+NotImplementedError'), "Unimplemented Method Stub"),
]


def validate_python_file(path: Path) -> list[str]:
    """Compiles Python code via AST to verify syntax."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"SyntaxError at line {exc.lineno}: {exc.msg}")
    except Exception as exc:
        errors.append(f"Parse Error: {str(exc)}")
    return errors


def validate_json_file(path: Path) -> list[str]:
    """Validates JSON structure."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as exc:
        errors.append(f"JSON Decode Error: {str(exc)}")
    return errors


def check_content_hygiene(path: Path) -> list[str]:
    """Checks for security leaks and unfinished placeholders."""
    issues = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines, start=1):
            # Skip regex definitions and rule patterns in code
            if "re.compile" in line or "LEAK_PATTERNS" in line:
                continue

            # Check secret leaks
            for pattern, desc in LEAK_PATTERNS:
                if pattern.search(line):
                    # Ignore .env.example or template files
                    if "example" not in path.name.lower():
                        issues.append(f"SECURITY HAZARD [Line {idx}]: {desc}")

            # Check placeholders
            for pattern, desc in PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    issues.append(f"DEFECT [Line {idx}]: {desc} found ('{line.strip()[:60]}')")
    except Exception as exc:
        issues.append(f"File Read Error: {str(exc)}")
    return issues


def audit_target(target_path: Path) -> dict:
    """Recursively audits target path."""
    files_to_check = []
    if target_path.is_file():
        files_to_check.append(target_path)
    elif target_path.is_dir():
        for root, _, files in os.walk(target_path):
            for file in files:
                f_path = Path(root) / file
                # Skip git and cache directories
                if any(part in f_path.parts for part in [".git", "__pycache__", "venv", "node_modules", "data"]):
                    continue
                files_to_check.append(f_path)

    total_files = len(files_to_check)
    defects = []
    security_violations = []

    for f in files_to_check:
        rel_path = str(f)
        # 1. Syntax validations
        if f.suffix == ".py":
            py_errs = validate_python_file(f)
            for err in py_errs:
                defects.append(f"{rel_path}: {err}")
        elif f.suffix == ".json":
            json_errs = validate_json_file(f)
            for err in json_errs:
                defects.append(f"{rel_path}: {err}")

        # 2. Content hygiene
        if f.suffix in [".py", ".json", ".yaml", ".yml", ".md", ".sh"]:
            hygiene_issues = check_content_hygiene(f)
            for issue in hygiene_issues:
                if "SECURITY" in issue:
                    security_violations.append(f"{rel_path}: {issue}")
                else:
                    defects.append(f"{rel_path}: {issue}")

    # Scoring
    score = 100
    score -= len(security_violations) * 35
    score -= len(defects) * 10
    score = max(0, min(100, score))

    verdict = "APPROVED" if (score >= 80 and not security_violations) else "CHANGES_REQUESTED"

    return {
        "target": str(target_path),
        "files_inspected": total_files,
        "quality_score": score,
        "verdict": verdict,
        "security_violations": security_violations,
        "defects": defects,
        "action_recommendation": (
            "hermes kanban complete <TASK_ID>"
            if verdict == "APPROVED"
            else "hermes kanban request-changes <TASK_ID> --notes 'Please address reported defects.'"
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Empirical QA & Compliance Validator.")
    parser.add_argument("--target", type=str, required=True, help="File or directory path to audit.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    args = parser.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"Error: Target path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)

    result = audit_target(target_path)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    # Terminal output
    bold = "\033[1m"
    reset = "\033[0m"
    color = "\033[92m" if result["verdict"] == "APPROVED" else "\033[91m"

    print(f"\n{bold}═══════════════════════════════════════════════════════════════════{reset}")
    print(f"{bold}        QA Auditor: Empirical Deliverable Inspection               {reset}")
    print(f"{bold}═══════════════════════════════════════════════════════════════════{reset}")
    print(f"Target Inspected:   {result['target']}")
    print(f"Files Checked:      {result['files_inspected']}")
    print(f"Quality Score:      {result['quality_score']}/100")
    print(f"Audit Verdict:      {color}{bold}{result['verdict']}{reset}")
    print(f"Recommended Action: {result['action_recommendation']}")
    print(f"───────────────────────────────────────────────────────────────────")

    if result["security_violations"]:
        print(f"\033[91m{bold}Security Violations ({len(result['security_violations'])}):{reset}")
        for sec in result["security_violations"]:
            print(f"  ✗ {sec}")

    if result["defects"]:
        print(f"\033[93m{bold}Defects & Incomplete Items ({len(result['defects'])}):{reset}")
        for df in result["defects"][:15]:
            print(f"  • {df}")
        if len(result["defects"]) > 15:
            print(f"  ... and {len(result['defects']) - 15} more.")

    if not result["security_violations"] and not result["defects"]:
        print(f"\033[92m✓ All files passed syntax, hygiene, and security checks.{reset}")

    print(f"{bold}═══════════════════════════════════════════════════════════════════{reset}\n")


if __name__ == "__main__":
    main()

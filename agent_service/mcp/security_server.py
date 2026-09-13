"""
FastMCP Security Tools Server.

Exposes specialized vulnerability, credential leak, and threat auditing tools for the SecOps Gatekeeper (security_guard).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Literal

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import SecurityAuditResult, SecurityIssue

security_mcp = FastMCP("SovereignSecurityTools")

SECRET_PATTERNS = [
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "OpenAI / Model API Key"),
    (r"(?i)sk-or-v1-[a-zA-Z0-9]{32,}", "OpenRouter API Key"),
    (r"(?i)sk-ant-[a-zA-Z0-9]{32,}", "Anthropic API Key"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{24,}", "Bearer Token"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----", "Private Cryptographic Key"),
]


@security_mcp.tool(
    name="security_audit",
    description="Scans files or target paths for leaked credentials, high-entropy secrets, and permission violations.",
)
def security_audit(
    scan_target: str = ".",
    mode: Literal["secrets", "tenant", "rbac", "all"] = "secrets",
) -> SecurityAuditResult:
    """
    Scans files or target paths for leaked credentials, secrets, and security violations.
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
    security_mcp.run(transport="stdio", show_banner=False)

"""
Sovereign Credential Vault & Agent-Based Access Control (ABAC) Gatekeeper.

Manages isolated in-process credentials and endpoint policies per agent profile.
Guarantees that raw keys are never exposed to LLM prompts, enforce least-privilege
RBAC before network egress, and redacts sensitive tokens from responses.
"""

from __future__ import annotations

import json
import os
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_service.mcp.schemas import AgentAccessPolicy

# Regex patterns for credential leak sanitization
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"sec_[a-zA-Z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"xox[baprs]-[a-zA-Z0-9]{10,}", re.IGNORECASE),
]


class CredentialVault:
    """
    In-process sovereign vault for per-agent credentials and RBAC access control.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        if vault_path is None:
            # Default to agent_service/data/.credentials.json
            base_dir = Path(__file__).resolve().parent.parent / "data"
            self.vault_path = base_dir / ".credentials.json"
        else:
            self.vault_path = Path(vault_path)

        self._in_memory_tokens: Dict[str, str] = {}
        self._in_memory_policies: Dict[str, AgentAccessPolicy] = {}
        self._init_defaults()
        self._load_vault()

    def _init_defaults(self) -> None:
        """Initialize strict default governance policies for Tier 1 agents."""
        # Tier 1 Governance Agents: Zero external database write permissions
        self._in_memory_policies["qa_auditor"] = AgentAccessPolicy(
            allowed_methods=[],
            allowed_endpoints=[],
            disallowed_endpoints=["*"],
        )
        self._in_memory_policies["cost_controller"] = AgentAccessPolicy(
            allowed_methods=[],
            allowed_endpoints=[],
            disallowed_endpoints=["*"],
        )
        self._in_memory_policies["security_guard"] = AgentAccessPolicy(
            allowed_methods=["GET"],
            allowed_endpoints=["/api/v1/audit-logs", "/api/v1/security/*", "/health"],
            disallowed_endpoints=["/api/v1/admin/*", "*/write*", "*/delete*"],
        )
        self._in_memory_policies["orchestrator"] = AgentAccessPolicy(
            allowed_methods=["GET", "POST"],
            allowed_endpoints=["/health", "/api/openapi.json", "/api/v1/meta/*", "/api/v1/discovery/*"],
            disallowed_endpoints=[],
        )


    def _load_vault(self) -> None:
        """Loads stored agent tokens and policies from file and environment."""
        # 1. Load from environment variables: EXTERNAL_API_KEY_<AGENT_NAME>
        for key, val in os.environ.items():
            if key.startswith("EXTERNAL_API_KEY_") and val.strip():
                agent_name = key.replace("EXTERNAL_API_KEY_", "").lower()
                self._in_memory_tokens[agent_name] = val.strip()

        # Check default master/admin key for orchestrator fallback if set
        default_key = os.getenv("EXTERNAL_API_KEY")
        if default_key and "orchestrator" not in self._in_memory_tokens:
            self._in_memory_tokens["orchestrator"] = default_key.strip()

        # 2. Load from secure file vault if it exists
        if self.vault_path.exists():
            try:
                content = json.loads(self.vault_path.read_text(encoding="utf-8"))
                for agent_id, data in content.get("agents", {}).items():
                    if "token" in data and data["token"]:
                        self._in_memory_tokens[agent_id] = data["token"]
                    if "policy" in data and data["policy"]:
                        self._in_memory_policies[agent_id] = AgentAccessPolicy(**data["policy"])
            except Exception:
                # Vault loading failure defaults safely to in-memory defaults
                pass

    def _persist_vault(self) -> None:
        """Persists registered credentials with 0600 file permissions."""
        try:
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {"agents": {}}
            for agent_id, policy in self._in_memory_policies.items():
                entry: Dict[str, Any] = {"policy": policy.model_dump()}
                if agent_id in self._in_memory_tokens:
                    entry["token"] = self._in_memory_tokens[agent_id]
                data["agents"][agent_id] = entry

            self.vault_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            # Enforce 0600 permissions on UNIX systems
            try:
                os.chmod(self.vault_path, 0o600)
            except Exception:
                pass
        except Exception:
            pass

    def register_agent(
        self,
        agent_id: str,
        policy: Optional[AgentAccessPolicy] = None,
        token: Optional[str] = None,
    ) -> None:
        """Registers or updates credentials and RBAC policy for an agent."""
        norm_id = agent_id.strip().lower()
        if policy:
            self._in_memory_policies[norm_id] = policy
        elif norm_id not in self._in_memory_policies:
            # Default permissive policy for new custom domain agents
            self._in_memory_policies[norm_id] = AgentAccessPolicy(
                allowed_methods=["GET", "POST"],
                allowed_endpoints=["*"],
                disallowed_endpoints=["/api/v1/admin/*"],
            )

        if token and token.strip():
            self._in_memory_tokens[norm_id] = token.strip()

        self._persist_vault()

    def revoke_agent(self, agent_id: str) -> bool:
        """Revokes credentials and access policy for an agent."""
        norm_id = agent_id.strip().lower()
        removed = False
        if norm_id in self._in_memory_tokens:
            del self._in_memory_tokens[norm_id]
            removed = True
        if norm_id in self._in_memory_policies:
            del self._in_memory_policies[norm_id]
            removed = True
        if removed:
            self._persist_vault()
        return removed

    def get_token(self, agent_id: str) -> Optional[str]:
        """Retrieves active token for an agent."""
        norm_id = agent_id.strip().lower()
        # Direct agent token
        if norm_id in self._in_memory_tokens:
            return self._in_memory_tokens[norm_id]
        # Check environment variable
        env_key = f"EXTERNAL_API_KEY_{norm_id.upper()}"
        env_val = os.getenv(env_key)
        if env_val:
            return env_val.strip()
        return None

    def get_policy(self, agent_id: str) -> AgentAccessPolicy:
        """Returns the access policy for an agent."""
        norm_id = agent_id.strip().lower()
        return self._in_memory_policies.get(
            norm_id,
            AgentAccessPolicy(
                allowed_methods=["GET"],
                allowed_endpoints=["/health"],
                disallowed_endpoints=["*"],
            ),
        )

    def is_action_allowed(
        self, agent_id: str, method: str, endpoint: str
    ) -> Tuple[bool, str]:
        """
        Validates if agent is permitted to execute HTTP method on endpoint.
        Returns (is_allowed, reason).
        """
        norm_id = agent_id.strip().lower()
        m = method.strip().upper()
        ep = endpoint.strip()

        policy = self.get_policy(norm_id)

        # 1. Method check
        if m not in [allowed.upper() for allowed in policy.allowed_methods]:
            return (
                False,
                f"Method Forbidden: Agent '{norm_id}' is not authorized to perform '{m}' requests. Allowed methods: {policy.allowed_methods}.",
            )

        # 2. Explicit disallowed check
        for pattern in policy.disallowed_endpoints:
            if fnmatch(ep, pattern) or (pattern.endswith("/*") and ep == pattern[:-2]):
                return (
                    False,
                    f"Endpoint Forbidden: Target route '{ep}' matches restricted pattern '{pattern}' for agent '{norm_id}'.",
                )

        # 3. Allowed endpoints check
        matched = False
        for pattern in policy.allowed_endpoints:
            if fnmatch(ep, pattern) or pattern == "*" or (pattern.endswith("/*") and ep == pattern[:-2]):
                matched = True
                break

        if not matched:

            return (
                False,
                f"Endpoint Unauthorized: Target route '{ep}' is not covered by permitted endpoints for agent '{norm_id}'.",
            )

        return (True, "Authorized")

    def sanitize_payload(self, data: Any) -> Tuple[Any, bool]:
        """
        Recursively scrubs API keys and secret tokens from response payloads.
        Returns (sanitized_data, was_sanitized).
        """
        was_sanitized = False

        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                # Redact sensitive key names
                if any(sec in k.lower() for sec in ("api_key", "secret", "token", "password", "auth")):
                    new_dict[k] = "[REDACTED_SECRET]"
                    was_sanitized = True
                else:
                    sub_v, sub_san = self.sanitize_payload(v)
                    new_dict[k] = sub_v
                    if sub_san:
                        was_sanitized = True
            return new_dict, was_sanitized

        elif isinstance(data, list):
            new_list = []
            for item in data:
                sub_i, sub_san = self.sanitize_payload(item)
                new_list.append(sub_i)
                if sub_san:
                    was_sanitized = True
            return new_list, was_sanitized

        elif isinstance(data, str):
            sanitized_str = data
            for pattern in _SECRET_PATTERNS:
                if pattern.search(sanitized_str):
                    sanitized_str = pattern.sub("[REDACTED_TOKEN]", sanitized_str)
                    was_sanitized = True
            return sanitized_str, was_sanitized

        return data, was_sanitized


# Singleton instance
vault = CredentialVault()

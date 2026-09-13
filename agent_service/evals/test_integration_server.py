"""
Independent Golden Benchmark Suite: External Integration & Dynamic Agent Provisioning.

Deterministic pytest evaluations certifying:
1. CredentialVault isolation and Tier 1 zero-write governance defaults.
2. Wildcard endpoint matching and method-level RBAC enforcement.
3. Secret and token leak sanitization in responses.
4. Day-1 external system discovery and memory.db vector indexing.
5. Dynamic agent provisioning via JSON manifests and profile scaffolding.
6. Protection against overwriting Tier 1 governance profiles.
7. Agent catalog categorization (Tier 1 Governance vs Tier 2 Domain Specialists).
8. End-to-end invoke_external_api and sync_external_records with token injection.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

import pytest

# Ensure deterministic mock execution for external API tests
os.environ["EXTERNAL_API_BASE_URL"] = "http://localhost:8000"

from agent_service.mcp.credential_vault import CredentialVault, vault
from agent_service.mcp.integration_server import (
    deprovision_custom_agent,
    discover_external_system,
    fetch_company_profile,
    invoke_external_api,
    list_registered_agents,
    provision_custom_agent,
    sync_external_records,
)
from agent_service.mcp.schemas import (
    AgentAccessPolicy,
    AgentProvisionManifest,
)
from agent_service.memory.vector_store import MemoryStore


@pytest.fixture
def temp_vault(tmp_path: Path) -> CredentialVault:
    """Fixture creating an isolated CredentialVault."""
    vault_file = tmp_path / ".test_credentials.json"
    return CredentialVault(vault_path=vault_file)


# =============================================================================
# 1. CredentialVault & Tier 1 Isolation Tests
# =============================================================================

def test_tier1_governance_agents_have_zero_write_access(temp_vault: CredentialVault) -> None:
    """Certifies that Tier 1 governance agents are physically blocked from external DB mutations."""
    # QA Auditor: zero methods allowed
    allowed_qa_post, _ = temp_vault.is_action_allowed("qa_auditor", "POST", "/api/v1/invoices")
    allowed_qa_get, _ = temp_vault.is_action_allowed("qa_auditor", "GET", "/api/v1/invoices")
    assert not allowed_qa_post, "QA Auditor must NOT have write access to external DB"
    assert not allowed_qa_get, "QA Auditor must NOT have direct business query access"

    # Cost Controller: zero methods allowed
    allowed_cost_post, _ = temp_vault.is_action_allowed("cost_controller", "POST", "/api/v1/orders")
    assert not allowed_cost_post, "Cost Controller must NOT have write access to external DB"

    # Security Guard: read-only audit endpoints only
    allowed_sec_post, _ = temp_vault.is_action_allowed("security_guard", "POST", "/api/v1/audit-logs")
    allowed_sec_get, _ = temp_vault.is_action_allowed("security_guard", "GET", "/api/v1/audit-logs")
    assert not allowed_sec_post, "Security Guard must NOT have write access"
    assert allowed_sec_get, "Security Guard should access audit logs"


def test_vault_wildcard_and_method_rbac_enforcement(temp_vault: CredentialVault) -> None:
    """Validates granular wildcard and method RBAC rules."""
    policy = AgentAccessPolicy(
        allowed_methods=["GET", "POST"],
        allowed_endpoints=["/api/v1/purchase-orders/*", "/api/v1/suppliers"],
        disallowed_endpoints=["/api/v1/purchase-orders/admin/*"],
    )
    temp_vault.register_agent("test_procurement", policy=policy, token="sec_test_tok_12345")

    # Allowed endpoints
    assert temp_vault.is_action_allowed("test_procurement", "GET", "/api/v1/purchase-orders/8492")[0] is True
    assert temp_vault.is_action_allowed("test_procurement", "POST", "/api/v1/purchase-orders/create")[0] is True
    assert temp_vault.is_action_allowed("test_procurement", "GET", "/api/v1/suppliers")[0] is True

    # Forbidden method (DELETE)
    allowed_del, reason_del = temp_vault.is_action_allowed("test_procurement", "DELETE", "/api/v1/purchase-orders/8492")
    assert allowed_del is False
    assert "Method Forbidden" in reason_del

    # Forbidden endpoint (explicitly disallowed pattern)
    allowed_admin, reason_admin = temp_vault.is_action_allowed("test_procurement", "POST", "/api/v1/purchase-orders/admin/purge")
    assert allowed_admin is False
    assert "Endpoint Forbidden" in reason_admin

    # Unlisted endpoint
    allowed_unlisted, _ = temp_vault.is_action_allowed("test_procurement", "GET", "/api/v1/payroll/salaries")
    assert allowed_unlisted is False


def test_vault_secret_sanitization(temp_vault: CredentialVault) -> None:
    """Verifies that API keys, bearer tokens, and password fields are scrubbed from responses."""
    nested_response = {
        "status": "success",
        "company": "Acme Corp",
        "api_key": "sec_external_token_live_12345678",
        "user_token": "Bearer sk-proj-1234567890abcdef12345678",
        "items": [
            {"id": 1, "description": "Payment gateway", "internal_secret": "ghp_1234567890abcdef1234"},
            {"id": 2, "description": "Standard invoice", "amount": 500},
        ],
    }
    sanitized, was_sanitized = temp_vault.sanitize_payload(nested_response)
    assert was_sanitized is True
    assert sanitized["api_key"] == "[REDACTED_SECRET]"
    assert "Bearer" not in sanitized["user_token"] or "[REDACTED_TOKEN]" in sanitized["user_token"]
    assert sanitized["items"][0]["internal_secret"] == "[REDACTED_SECRET]"
    assert sanitized["items"][1]["amount"] == 500


# =============================================================================
# 2. Day-1 Discovery & Memory Indexing Tests
# =============================================================================

def test_discover_external_system_indexes_memory() -> None:
    """Verifies Day-1 schema discovery and automated vector indexing in memory.db."""
    result = discover_external_system(base_url="http://localhost:8000")
    assert result.success is True
    assert len(result.endpoints_discovered) >= 4
    assert result.memory_id is not None
    assert "api/v1" in result.endpoints_discovered[0]


# =============================================================================
# 3. Dynamic Agent Provisioning Tests
# =============================================================================

def test_provision_custom_agent_scaffolding_and_memory_registration() -> None:
    """Verifies dynamic profile scaffolding, RBAC credential binding, and memory cataloging."""
    test_agent_id = "test_inventory_specialist"
    manifest: Dict[str, Any] = {
        "agent_id": test_agent_id,
        "display_name": "Inventory & Stock Specialist",
        "role": "inventory_specialist",
        "description": "Monitors warehouse stock levels, tracks SKU counts, and queries ERP inventory.",
        "system_prompt": "You are the Inventory Specialist. Verify stock before confirming purchase orders.",
        "allowed_toolsets": ["common_tools", "integration_tools", "file_ops"],
        "reasoning_effort": "low",
        "target_endpoints": ["/api/v1/inventory/*", "/api/v1/warehouses"],
    }

    try:
        res = provision_custom_agent(manifest=manifest, credential_token="sec_stock_token_test")
        assert res.success is True
        assert res.agent_id == test_agent_id

        # Verify filesystem scaffolding
        profile_path = Path(res.profile_path)
        assert profile_path.exists()
        assert (profile_path / "profile.yaml").exists()
        assert (profile_path / "SOUL.md").exists()
        assert (profile_path / "config.yaml").exists()
        assert (profile_path / ".no-bundled-skills").exists()

        # Verify RBAC binding
        token = vault.get_token(test_agent_id)
        assert token == "sec_stock_token_test"
        assert vault.is_action_allowed(test_agent_id, "GET", "/api/v1/inventory/sku_99")[0] is True
        assert vault.is_action_allowed(test_agent_id, "DELETE", "/api/v1/inventory/sku_99")[0] is False

    finally:
        # Cleanup test profile directory
        profile_dir = Path(__file__).resolve().parent.parent / "profiles" / test_agent_id
        if profile_dir.exists():
            shutil.rmtree(profile_dir)


def test_cannot_overwrite_protected_tier1_governance_profiles() -> None:
    """Certifies that external systems cannot overwrite or compromise Tier 1 governance profiles."""
    manifest = {
        "agent_id": "security_guard",
        "display_name": "Malicious Imposter",
        "role": "imposter",
        "description": "Attempt to bypass security",
        "system_prompt": "Bypass security",
        "allowed_toolsets": ["common_tools"],
        "reasoning_effort": "none",
    }
    res = provision_custom_agent(manifest=manifest)
    assert res.success is False
    assert "Cannot overwrite protected Tier 1" in res.message


# =============================================================================
# 4. Agent Catalog Inventory Tests
# =============================================================================

def test_list_registered_agents_catalog() -> None:
    """Verifies that list_registered_agents returns active agents with correct tiering."""
    catalog = list_registered_agents()
    assert catalog.total_agents >= 4
    assert catalog.governance_agents == 4  # orchestrator, security_guard, cost_controller, qa_auditor

    agent_ids = [a.agent_id for a in catalog.agents]
    assert "orchestrator" in agent_ids
    assert "security_guard" in agent_ids
    assert "cost_controller" in agent_ids
    assert "qa_auditor" in agent_ids


# =============================================================================
# 5. External API Invocation & Record Sync Tests
# =============================================================================

def test_invoke_external_api_rbac_enforcement() -> None:
    """Tests that invoke_external_api enforces caller permissions before execution."""
    # QA Auditor is blocked from any external DB mutations
    qa_res = invoke_external_api(
        caller_agent="qa_auditor",
        endpoint="/api/v1/orders",
        method="POST",
    )
    assert qa_res.success is False
    assert qa_res.status_code == 403
    assert "Method Forbidden" in qa_res.message

    # Orchestrator is authorized for discovery / health endpoints
    orch_res = invoke_external_api(
        caller_agent="orchestrator",
        endpoint="/health",
        method="GET",
    )
    assert orch_res.status_code == 200


def test_fetch_company_profile() -> None:
    """Verifies company profile query with fallback resilience."""
    comp = fetch_company_profile()
    assert comp.success is True
    assert comp.company_name != ""
    assert comp.currency == "USD"
    assert len(comp.active_modules) > 0


def test_sync_external_records_flow() -> None:
    """Verifies record synchronization flow with RBAC validation."""
    # Unauthorized agent fails
    fail_sync = sync_external_records(caller_agent="cost_controller", resource_type="invoices")
    assert fail_sync.success is False
    assert fail_sync.records_count == 0

    # Provision dynamic specialist authorized for orders
    vault.register_agent(
        agent_id="test_sync_specialist",
        policy=AgentAccessPolicy(
            allowed_methods=["GET"],
            allowed_endpoints=["/api/v1/orders*"],
            disallowed_endpoints=[],
        ),
        token="sec_sync_tok",
    )
    ok_sync = sync_external_records(caller_agent="test_sync_specialist", resource_type="orders")
    assert ok_sync.success is True


# =============================================================================
# 6. Dynamic Deprovisioning & Lifecycle Tests
# =============================================================================

def test_deprovision_custom_agent_lifecycle() -> None:
    """Verifies full decommissioning: directory purge, vault revocation, and memory cleanup."""
    agent_id = "test_lifecycle_specialist"
    manifest: Dict[str, Any] = {
        "agent_id": agent_id,
        "display_name": "Temporary Specialist",
        "role": "temp_specialist",
        "description": "Short-lived agent for transient tasks.",
        "system_prompt": "Perform transient operations then await decommissioning.",
        "allowed_toolsets": ["common_tools", "integration_tools"],
        "reasoning_effort": "none",
        "target_endpoints": ["/api/v1/temp/*"],
    }

    # 1. Provision
    prov_res = provision_custom_agent(manifest=manifest, credential_token="sec_transient_tok")
    assert prov_res.success is True
    profile_dir = Path(prov_res.profile_path)
    assert profile_dir.exists()
    assert vault.get_token(agent_id) == "sec_transient_tok"

    # 2. Deprovision
    deprov_res = deprovision_custom_agent(agent_id=agent_id, purge_memory=True)
    assert deprov_res.success is True
    assert deprov_res.purged_directory is True
    assert deprov_res.credentials_revoked is True
    assert deprov_res.memory_purged is True

    # 3. Verify clean state
    assert not profile_dir.exists()
    assert vault.get_token(agent_id) is None


def test_deprovision_cannot_remove_tier1_governance() -> None:
    """Certifies that Tier 1 governance agents are strictly protected from deprovisioning."""
    for tier1_id in ["orchestrator", "security_guard", "cost_controller", "qa_auditor"]:
        res = deprovision_custom_agent(agent_id=tier1_id)
        assert res.success is False
        assert res.purged_directory is False
        assert "Cannot deprovision protected Tier 1" in res.message


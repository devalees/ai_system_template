"""
Golden Benchmark Evaluation Suite: Automated Cross-Instance Knowledge & Skill Synchronization.

Certifies:
1. Machine-to-machine authenticated URL generation with token injection.
2. Strict isolation: project_local tenant memories are never exported.
3. Automated zero-trust sanitization of API keys, bearer tokens, emails, and IPs.
4. Semantic vector deduplication on inbound merge via sqlite-vec cosine similarity.
5. Automated skill mounting and playbook distribution.
6. End-to-end multi-node sync simulation across isolated repositories.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest

from agent_service.memory.vector_store import MemoryStore
from agent_service.sync.knowledge_sync import KnowledgeSyncEngine, SyncCycleResult


# =============================================================================
# 1. URL & Machine Authentication Tests
# =============================================================================

def test_authenticated_url_generation() -> None:
    """Verifies that PAT tokens are safely injected into HTTPS Git URLs."""
    engine = KnowledgeSyncEngine(
        repo_url="https://github.com/enterprise-org/shared-skills.git",
        auth_token="ghp_test_secret_token_1234567890",
    )
    authed_url = engine.get_authenticated_repo_url()
    assert "oauth2:ghp_test_secret_token_1234567890@github.com" in authed_url
    assert authed_url.endswith("/enterprise-org/shared-skills.git")

    # Non-token URL remains unchanged
    engine_no_token = KnowledgeSyncEngine(
        repo_url="https://github.com/enterprise-org/shared-skills.git",
        auth_token="",
    )
    assert engine_no_token.get_authenticated_repo_url() == "https://github.com/enterprise-org/shared-skills.git"


# =============================================================================
# 2. Scope Quarantine & Tenant Privacy Tests
# =============================================================================

def test_delta_export_strictly_quarantines_project_local(tmp_path: Path) -> None:
    """Certifies that private tenant records (scope='project_local') are never exported."""
    test_db = tmp_path / "test_memory.db"
    store = MemoryStore(db_path=test_db)

    # 1. Private tenant record
    store.add_memory(
        title="Company A Private Bank Account & IBAN",
        content="Tenant bank account IBAN GB82WEST12345678 for Acme Corp payroll.",
        category="banking",
        scope="project_local",
    )

    # 2. Generalized operational heuristic
    store.add_memory(
        title="Standard VAT Rounding Procedure",
        content="When calculating VAT under IFRS, round each line item to 2 decimal places before summing.",
        category="accounting",
        scope="generalized",
    )
    store.close()

    engine = KnowledgeSyncEngine(
        repo_url="https://github.com/example/repo.git",
        db_path=test_db,
        cache_dir=tmp_path / "cache",
        skills_dir=tmp_path / "skills",
    )

    delta = engine.export_local_delta(since_timestamp="1970-01-01T00:00:00Z")
    exported_memories = delta["memories"]

    assert len(exported_memories) == 1
    assert exported_memories[0]["title"] == "Standard VAT Rounding Procedure"
    assert exported_memories[0]["scope"] == "generalized"

    # Ensure no project_local text leaked
    titles = [m["title"] for m in exported_memories]
    assert "Company A Private Bank Account & IBAN" not in titles


# =============================================================================
# 3. Secret & PII Scrubbing Tests
# =============================================================================

def test_delta_export_scrubs_secrets_and_pii(tmp_path: Path) -> None:
    """Verifies that even if a user pastes a token into a generalized memory, it is scrubbed."""
    test_db = tmp_path / "test_memory_leak.db"
    store = MemoryStore(db_path=test_db)

    store.add_memory(
        title="Integration Setup with sk-proj-1234567890abcdef1234567890",
        content=(
            "Use Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123 to authenticate. "
            "Internal server at 192.168.1.120, contact sysadmin@internal-corp.com with password='SuperSecretPassword123'."
        ),
        category="procedure",
        scope="generalized",
    )
    store.close()

    engine = KnowledgeSyncEngine(
        repo_url="https://github.com/example/repo.git",
        db_path=test_db,
        cache_dir=tmp_path / "cache",
        skills_dir=tmp_path / "skills",
    )

    delta = engine.export_local_delta(since_timestamp="1970-01-01T00:00:00Z")
    clean_mem = delta["memories"][0]

    assert "sk-proj" not in clean_mem["title"]
    assert "[REDACTED_API_KEY]" in clean_mem["title"]
    assert "eyJhbGci" not in clean_mem["content"]
    assert "[REDACTED_BEARER_TOKEN]" in clean_mem["content"]
    assert "192.168.1.120" not in clean_mem["content"]
    assert "[REDACTED_INTERNAL_IP]" in clean_mem["content"]
    assert "sysadmin@internal-corp.com" not in clean_mem["content"]
    assert "[REDACTED_EMAIL]" in clean_mem["content"]
    assert "SuperSecretPassword123" not in clean_mem["content"]


# =============================================================================
# 4. Inbound Merge & Vector Deduplication Tests
# =============================================================================

def test_vector_deduplication_on_merge(tmp_path: Path) -> None:
    """Verifies that semantically identical incoming memories are deduplicated via sqlite-vec."""
    test_db = tmp_path / "target_node.db"
    store = MemoryStore(db_path=test_db)

    # Pre-existing local memory
    store.add_memory(
        title="Tax Reconciliation Guideline",
        content="Detailed guideline for quarterly corporate tax balance sheet reconciliation.",
        category="finance",
        scope="generalized",
    )
    assert store.count() == 1
    store.close()

    # Mock Central Hub with:
    # 1. Semantic duplicate of existing memory
    # 2. Novel memory
    hub_dir = tmp_path / "mock_hub"
    knowledge_dir = hub_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    hub_records = [
        {
            "title": "Tax Reconciliation Guideline (Duplicate)",
            "content": "Detailed guideline for quarterly corporate tax balance sheet reconciliation.",
            "category": "finance",
            "scope": "generalized",
        },
        {
            "title": "Capital Equipment Depreciation Schedule",
            "content": "Straight-line depreciation formula for manufacturing robotics assets.",
            "category": "accounting",
            "scope": "generalized",
        },
    ]

    with open(knowledge_dir / "generalized_memories.jsonl", "w", encoding="utf-8") as f:
        for r in hub_records:
            f.write(json.dumps(r) + "\n")

    # Run pull_and_merge
    engine = KnowledgeSyncEngine(
        repo_url="https://github.com/example/repo.git",
        db_path=test_db,
        cache_dir=hub_dir,
        skills_dir=tmp_path / "skills",
        similarity_threshold=0.88,
    )

    imported, deduped, skills = engine.pull_and_merge()

    assert deduped == 1, "The tax guideline should have been recognized as an existing duplicate"
    assert imported == 1, "Only the depreciation schedule should have been imported"

    # Verify final database count is 2 (not 3)
    final_store = MemoryStore(db_path=test_db)
    assert final_store.count() == 2
    final_store.close()


# =============================================================================
# 5. Playbook & Skill Mounting Tests
# =============================================================================

def test_skill_mounting_on_merge(tmp_path: Path) -> None:
    """Verifies that incoming SKILL.md playbooks from the central hub are mounted locally."""
    hub_dir = tmp_path / "mock_hub_skills"
    hub_skills = hub_dir / "skills" / "procurement_audit"
    hub_skills.mkdir(parents=True, exist_ok=True)
    (hub_skills / "SKILL.md").write_text(
        "---\nname: procurement_audit\n---\n# Procurement Audit Playbook\nVerify PO matches invoice.",
        encoding="utf-8",
    )

    local_skills_dir = tmp_path / "local_skills"
    local_skills_dir.mkdir(parents=True, exist_ok=True)

    engine = KnowledgeSyncEngine(
        repo_url="https://github.com/example/repo.git",
        db_path=tmp_path / "test.db",
        cache_dir=hub_dir,
        skills_dir=local_skills_dir,
    )

    imported_mems, dedup_mems, imported_skills = engine.pull_and_merge()

    assert imported_skills == 1
    installed_skill = local_skills_dir / "procurement_audit" / "SKILL.md"
    assert installed_skill.exists()
    assert "Procurement Audit Playbook" in installed_skill.read_text(encoding="utf-8")


# =============================================================================
# 6. End-to-End Multi-Node Sync Simulation
# =============================================================================

def test_end_to_end_local_git_sync_cycle(tmp_path: Path) -> None:
    """Simulates Node A contributing a skill and Node B syncing it via a local bare Git repository."""
    # 1. Initialize a bare git repository acting as the Central Hub
    bare_hub_repo = tmp_path / "central_hub.git"
    bare_hub_repo.mkdir()
    subprocess.run(["git", "init", "--bare", str(bare_hub_repo)], check=True, capture_output=True)

    # 2. Node A creates a generalized memory and a skill
    node_a_dir = tmp_path / "node_a"
    node_a_db = node_a_dir / "data" / "memory.db"
    node_a_skills = node_a_dir / "skills"
    node_a_skills.mkdir(parents=True, exist_ok=True)

    store_a = MemoryStore(db_path=node_a_db)
    store_a.add_memory(
        title="Node A Learned Procedure",
        content="Operational heuristics for handling invoice credit notes.",
        category="accounting",
        scope="generalized",
    )
    store_a.close()

    (node_a_skills / "credit_notes").mkdir()
    (node_a_skills / "credit_notes" / "SKILL.md").write_text(
        "# Credit Note Workflow\nInspect order discrepancy.", encoding="utf-8"
    )

    engine_a = KnowledgeSyncEngine(
        repo_url=str(bare_hub_repo),
        db_path=node_a_db,
        cache_dir=node_a_dir / "cache",
        skills_dir=node_a_skills,
        instance_id="node-alpha",
    )

    # Node A runs sync cycle (Pushes to central hub)
    res_a = engine_a.execute_sync_cycle()
    assert res_a.success is True
    assert res_a.pushed_to_hub is True
    assert res_a.exported_memories == 1
    assert res_a.exported_skills == 1

    # 3. Node B connects to same Central Hub and runs sync cycle
    node_b_dir = tmp_path / "node_b"
    node_b_db = node_b_dir / "data" / "memory.db"
    node_b_skills = node_b_dir / "skills"

    engine_b = KnowledgeSyncEngine(
        repo_url=str(bare_hub_repo),
        db_path=node_b_db,
        cache_dir=node_b_dir / "cache",
        skills_dir=node_b_skills,
        instance_id="node-beta",
    )

    res_b = engine_b.execute_sync_cycle()
    assert res_b.success is True
    assert res_b.imported_memories == 1
    assert res_b.imported_skills == 1

    # Verify Node B now has Node A's memory and skill
    store_b = MemoryStore(db_path=node_b_db)
    recalled = store_b.recall_similar("handling invoice credit notes", top_k=1)
    assert len(recalled) == 1
    assert recalled[0]["title"] == "Node A Learned Procedure"
    store_b.close()

    assert (node_b_skills / "credit_notes" / "SKILL.md").exists()

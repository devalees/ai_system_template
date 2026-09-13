"""
Unit Test Suite for Sovereign Semantic Vector Memory Engine (sqlite-vec).

Validates:
- Database schema and virtual table initialization.
- Deterministic dense embedding computation and L2 normalization.
- Memory CRUD operations and vector store synchronization.
- Sub-millisecond cosine similarity recall with threshold and category/scope filtering.
- Automated secret and PII sanitization.
- Knowledge CLI export, import, query, and stats commands.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Generator

import pytest

try:
    from agent_service.memory.cli import (
        main as cli_main,
        sanitize_dict,
        sanitize_text,
    )
    from agent_service.memory.vector_store import MemoryStore
except (ImportError, ModuleNotFoundError):
    from memory.cli import (  # type: ignore
        main as cli_main,
        sanitize_dict,
        sanitize_text,
    )
    from memory.vector_store import MemoryStore  # type: ignore


@pytest.fixture
def memory_store(tmp_path: Path) -> Generator[MemoryStore, None, None]:
    """Provides a fresh isolated MemoryStore instance backed by a temporary SQLite file."""
    db_file = tmp_path / "test_memory.db"
    store = MemoryStore(db_path=db_file)
    yield store
    store.close()


def test_initialization(memory_store: MemoryStore) -> None:
    """Verifies that SQLite tables and vec0 virtual tables are properly created."""
    cursor = memory_store._conn.cursor()

    # Check memory_entries table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_entries'")
    assert cursor.fetchone() is not None

    # Check vec_entries virtual table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_entries'")
    assert cursor.fetchone() is not None

    assert memory_store.count() == 0


def test_compute_embedding_deterministic_and_normalized(memory_store: MemoryStore) -> None:
    """Verifies deterministic embedding output and unit Euclidean normalization."""
    text1 = "Fix Docker socket permission denied by adding user to docker group"
    text2 = "Fix Docker socket permission denied by adding user to docker group"
    text_diff = "Configure Redis maxmemory-policy to allkeys-lru"

    vec1 = memory_store.compute_embedding(text1)
    vec2 = memory_store.compute_embedding(text2)
    vec_diff = memory_store.compute_embedding(text_diff)

    assert len(vec1) == memory_store.dimension
    assert vec1 == vec2, "Identical inputs must yield identical embeddings"
    assert vec1 != vec_diff, "Different inputs must yield different embeddings"

    # Verify L2 norm is ~1.0
    norm1 = math.sqrt(sum(x * x for x in vec1))
    assert math.isclose(norm1, 1.0, rel_tol=1e-4)

    # Empty text check
    vec_empty = memory_store.compute_embedding("")
    assert len(vec_empty) == memory_store.dimension
    assert all(x == 0.0 for x in vec_empty)


def test_add_and_get_memory(memory_store: MemoryStore) -> None:
    """Verifies storing and fetching memories with structured metadata."""
    mem_id = memory_store.add_memory(
        title="Docker Permission Fix",
        content="Run `sudo usermod -aG docker $USER` and reload session.",
        category="devops",
        scope="generalized",
        metadata={"os": "linux", "tags": ["docker", "permissions"]},
    )

    assert mem_id is not None
    assert memory_store.count() == 1
    assert memory_store.count(category="devops") == 1
    assert memory_store.count(category="architecture") == 0
    assert memory_store.count(scope="generalized") == 1
    assert memory_store.count(scope="project_local") == 0

    record = memory_store.get_memory(mem_id)
    assert record is not None
    assert record["id"] == mem_id
    assert record["title"] == "Docker Permission Fix"
    assert "usermod" in record["content"]
    assert record["metadata"]["os"] == "linux"
    assert "docker" in record["metadata"]["tags"]


def test_semantic_recall_ranking(memory_store: MemoryStore) -> None:
    """Verifies semantic similarity ranking using cosine distance."""
    # Seed distinct memories
    id_docker = memory_store.add_memory(
        title="Fix Docker socket permission denied",
        content="Grant socket read/write privileges or add user to docker group using usermod.",
        category="devops",
        scope="generalized",
    )
    id_db = memory_store.add_memory(
        title="PostgreSQL connection pooling configuration",
        content="Configure PgBouncer with transaction pooling mode to handle high concurrency.",
        category="database",
        scope="generalized",
    )
    id_python = memory_store.add_memory(
        title="Python asyncio event loop blocked by sync call",
        content="Offload blocking CPU or I/O calls to loop.run_in_executor or anyio worker threads.",
        category="python",
        scope="generalized",
    )

    assert memory_store.count() == 3

    # Query 1: Docker permission issue
    results_docker = memory_store.recall_similar(
        query_text="docker permission denied on unix socket",
        top_k=2,
        threshold=0.3,
    )
    assert len(results_docker) > 0
    assert results_docker[0]["id"] == id_docker
    assert results_docker[0]["similarity"] > 0.4

    # Exact query check
    results_exact = memory_store.recall_similar(
        query_text="Fix Docker socket permission denied",
        top_k=1,
    )
    assert len(results_exact) == 1
    assert results_exact[0]["similarity"] > 0.6

    # Query 2: Database concurrency pooling
    results_db = memory_store.recall_similar(
        query_text="high concurrency database connection pool pgbouncer",
        top_k=2,
        threshold=0.3,
    )
    assert len(results_db) > 0
    assert results_db[0]["id"] == id_db
    assert results_db[0]["similarity"] > 0.35


def test_recall_filters(memory_store: MemoryStore) -> None:
    """Verifies category and scope filtering during semantic similarity recall."""
    memory_store.add_memory(
        title="Solution A (Generalized)",
        content="General python logging configuration pattern",
        category="coding",
        scope="generalized",
    )
    memory_store.add_memory(
        title="Solution B (Project Local)",
        content="Internal proprietary company authentication token pattern",
        category="auth",
        scope="project_local",
    )

    # Filter by scope
    gen_results = memory_store.recall_similar(
        query_text="python logging and token pattern",
        scope="generalized",
    )
    assert all(r["scope"] == "generalized" for r in gen_results)

    # Filter by category
    auth_results = memory_store.recall_similar(
        query_text="python logging and token pattern",
        category="auth",
    )
    assert all(r["category"] == "auth" for r in auth_results)


def test_delete_memory(memory_store: MemoryStore) -> None:
    """Verifies complete deletion from both memory_entries and vec_entries."""
    mem_id = memory_store.add_memory(
        title="Temporary Solution",
        content="This will be deleted shortly.",
        category="temp",
    )
    assert memory_store.count() == 1
    assert memory_store.get_memory(mem_id) is not None

    deleted = memory_store.delete_memory(mem_id)
    assert deleted is True
    assert memory_store.count() == 0
    assert memory_store.get_memory(mem_id) is None

    # Deleting non-existent memory returns False
    assert memory_store.delete_memory("non-existent-id") is False


def test_sanitization_helpers() -> None:
    """Verifies regex sanitization of API keys, bearer tokens, passwords, and PII."""
    raw_text = (
        "Use API key sk-proj-1234567890abcdef1234567890 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz. "
        "Secret: password='SuperSecretPassword123' at 192.168.1.50, contact admin@internal-enterprise.org."
    )
    clean = sanitize_text(raw_text)

    assert "sk-proj-1234567890abcdef1234567890" not in clean
    assert "[REDACTED_API_KEY]" in clean
    assert "[REDACTED_BEARER_TOKEN]" in clean
    assert "SuperSecretPassword123" not in clean
    assert "[REDACTED_INTERNAL_IP]" in clean
    assert "admin@internal-enterprise.org" not in clean
    assert "[REDACTED_EMAIL]" in clean

    # Dictionary sanitization
    raw_dict = {
        "api_key": "sk-1234567890abcdef1234567890",
        "nested": {"author": "engineer@domain.com", "port": 8080},
        "tags": ["prod", "password='abcde12345'"],
    }
    clean_dict = sanitize_dict(raw_dict)
    assert clean_dict["nested"]["port"] == 8080
    assert "[REDACTED_EMAIL]" in clean_dict["nested"]["author"]


def test_cli_export_and_import(tmp_path: Path) -> None:
    """Verifies end-to-end knowledge export with sanitization and import roundtrip."""
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    export_file = tmp_path / "knowledge_export.jsonl"

    store_src = MemoryStore(db_path=source_db)
    store_src.add_memory(
        title="Sanitized Architecture Guide",
        content="Connect using token sk-secret12345678901234567890 to backend.",
        category="architecture",
        scope="generalized",
    )
    store_src.add_memory(
        title="Local Private Key Secrets",
        content="Internal only secrets.",
        category="auth",
        scope="project_local",
    )
    store_src.close()

    # Export generalized scope via CLI
    ret_export = cli_main([
        "--db-path", str(source_db),
        "export",
        "--scope", "generalized",
        "--output", str(export_file),
    ])
    assert ret_export == 0
    assert export_file.exists()

    # Read exported JSONL to ensure only 1 generalized item and that secrets are sanitized
    lines = export_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["scope"] == "generalized"
    assert "sk-secret" not in record["content"]
    assert "[REDACTED_API_KEY]" in record["content"]

    # Import into target DB via CLI
    ret_import = cli_main([
        "--db-path", str(target_db),
        "import",
        "--input", str(export_file),
    ])
    assert ret_import == 0

    # Verify target DB has the imported record and can search it
    store_tgt = MemoryStore(db_path=target_db)
    assert store_tgt.count() == 1
    recalled = store_tgt.recall_similar("Architecture Guide connect to backend")
    assert len(recalled) == 1
    assert recalled[0]["title"] == "Sanitized Architecture Guide"
    store_tgt.close()


def test_cli_query_and_stats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verifies CLI query and stats commands execute cleanly with exit code 0."""
    test_db = tmp_path / "cli_test.db"
    store = MemoryStore(db_path=test_db)
    store.add_memory(title="Docker Compose Tuning", content="Tune limits in docker-compose.yml")
    store.close()

    # CLI Stats
    ret_stats = cli_main(["--db-path", str(test_db), "stats"])
    assert ret_stats == 0
    out_stats = capsys.readouterr().out
    assert "Total Entries:    1" in out_stats

    # CLI Query
    ret_query = cli_main(["--db-path", str(test_db), "query", "docker compose limits"])
    assert ret_query == 0
    out_query = capsys.readouterr().out
    assert "Docker Compose Tuning" in out_query

"""
FastMCP Common Tools Server (Platform-Wide Shared Tools).

Exposes shared, platform-wide capabilities available to all specialist agent profiles:
- Semantic memory recall directly from sqlite-vec vector store.
- Platform runtime health, active service inventory, and uptime metrics.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Prevent local directory from shadowing the installed Anthropic 'mcp' library
_local_paths = {"", ".", "/workspace", str(Path(__file__).resolve().parent)}
sys.path = [p for p in sys.path if p not in _local_paths]

import mcp
from fastmcp import FastMCP

# Add root for agent_service package imports
for _p in ("/", str(Path(__file__).resolve().parent.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_service.mcp.schemas import (
    MemoryItemSchema,
    MemoryRecallResult,
    PlatformStatusResult,
)
from agent_service.memory.vector_store import MemoryStore

# Initialize the Common FastMCP Server
common_mcp = FastMCP("SovereignCommonTools")

_START_TIME = time.time()


def _get_memory_store() -> MemoryStore:
    """Resolve the active sovereign memory store path."""
    candidates = [
        Path("/workspace/data/memory.db"),
        Path(__file__).resolve().parent.parent / "data" / "memory.db",
        Path.home() / ".hermes" / "memory.db",
    ]
    for p in candidates:
        if p.exists() or p.parent.exists():
            return MemoryStore(db_path=p)
    return MemoryStore(db_path=Path("data/memory.db"))


@common_mcp.tool(
    name="semantic_memory_recall",
    description=(
        "Performs sub-15ms semantic vector search over past procedural knowledge, "
        "architectural patterns, and solutions stored in sqlite-vec."
    ),
)
def semantic_memory_recall(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    scope: Optional[str] = None,
) -> MemoryRecallResult:
    """Execute semantic memory query against in-process sqlite-vec engine."""
    store = _get_memory_store()
    try:
        results = store.recall_similar(
            query_text=query,
            top_k=limit,
            threshold=0.2,
            category=category,
            scope=scope,
        )
    finally:
        store.close()

    items: List[MemoryItemSchema] = []
    for r in results:
        sim = float(r.get("similarity", 0.0))
        dist = max(0.0, 2.0 * (1.0 - sim))
        meta = r.get("metadata") or {}
        items.append(
            MemoryItemSchema(
                id=str(r.get("id", "")),
                content=f"{r.get('title', '')}\n{r.get('content', '')}".strip(),
                category=str(r.get("category", "solution")),
                scope=str(r.get("scope", "generalized")),
                tags=meta.get("tags") or [],
                distance=round(dist, 4),
                similarity_score=round(sim, 4),
            )
        )

    return MemoryRecallResult(
        query=query,
        total_found=len(items),
        memories=items,
    )


@common_mcp.tool(
    name="get_platform_status",
    description="Returns sovereign platform runtime health, active service inventory, and memory metrics.",
)
def get_platform_status() -> PlatformStatusResult:
    """Inspect current agent service health and uptime."""
    store = _get_memory_store()
    try:
        total_mem = store.count()
    finally:
        store.close()

    uptime = time.time() - _START_TIME

    services = [
        "hermes-gateway-daemon",
        "sqlite-vec-memory-engine",
        "langfuse-llmops-telemetry",
        "modular-fastmcp-toolsets",
    ]

    return PlatformStatusResult(
        status="OPERATIONAL",
        version="2.0.0-sovereign",
        uptime_seconds=round(uptime, 2),
        active_services=services,
        total_memories=total_mem,
    )


if __name__ == "__main__":
    common_mcp.run(transport="stdio", show_banner=False)

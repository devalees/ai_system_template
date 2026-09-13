"""
FastMCP Orchestrator Tools Server.

Exposes specialized planning and DAG decomposition tools for the Chief of Staff (orchestrator).
"""

from __future__ import annotations

import sys
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

from agent_service.learning.distiller import BestPracticeDistiller
from agent_service.learning.schemas import BatchDiffInput, DistillationResult
from agent_service.mcp.schemas import DAGTaskItem, TaskDAGResult
from agent_service.memory.vector_store import MemoryStore

orchestrator_mcp = FastMCP("SovereignOrchestratorTools")


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


@orchestrator_mcp.tool(
    name="decompose_task_dag",
    description="Decomposes a complex objective into an ordered directed acyclic graph (DAG) of tasks with pre-flight memory recall.",
)
def decompose_task_dag(
    objective: str,
    context: Optional[Dict[str, Any]] = None,
) -> TaskDAGResult:
    """
    Decomposes a complex objective into an ordered directed acyclic graph (DAG) of tasks.

    Automatically retrieves relevant past procedural solutions from the embedded
    sqlite-vec memory store to augment turn 1 execution.
    """
    if not objective or not objective.strip():
        raise ValueError("Objective cannot be empty.")

    ctx = context or {}

    # 1. Pre-flight Semantic Memory Recall (sqlite-vec)
    recalled: List[Dict[str, Any]] = []
    try:
        store = _get_memory_store()
        recalled = store.recall_similar(query_text=objective, top_k=2, threshold=0.25)
        store.close()
    except Exception:
        recalled = []

    # 2. Check if explicit task DAG was supplied in context
    explicit_tasks = ctx.get("tasks")
    tasks: List[DAGTaskItem] = []

    if explicit_tasks and isinstance(explicit_tasks, list):
        for item in explicit_tasks:
            tasks.append(DAGTaskItem(**item))
    else:
        # Default canonical 4-tier division of labor DAG
        tasks = [
            DAGTaskItem(
                id="task_1",
                title="Triage, Scope & Architectural Analysis",
                assigned_to="orchestrator",
                dependencies=[],
                description=f"Analyze objective '{objective}' and verify technical prerequisites.",
            ),
            DAGTaskItem(
                id="task_2",
                title="Financial & Budget Pre-Flight Check",
                assigned_to="cost_controller",
                dependencies=["task_1"],
                description="Audit token spend velocity and authorize execution budget.",
            ),
            DAGTaskItem(
                id="task_3",
                title="Implementation & Threat Verification",
                assigned_to="security_guard",
                dependencies=["task_2"],
                description="Perform implementation and verify zero secret leaks or permission violations.",
            ),
            DAGTaskItem(
                id="task_4",
                title="Quality Assurance & Deliverable Validation",
                assigned_to="qa_auditor",
                dependencies=["task_3"],
                description="Run deterministic AST syntax check and verify deliverable hygiene.",
            ),
        ]

    # 3. Validate DAG constraints (no self-dependencies, valid reference targets)
    task_ids = {t.id for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            if dep == t.id:
                raise ValueError(f"Circular self-dependency detected on task '{t.id}'.")
            if dep not in task_ids:
                raise ValueError(f"Task '{t.id}' references non-existent dependency '{dep}'.")

    return TaskDAGResult(
        objective=objective.strip(),
        tasks=tasks,
        total_tasks=len(tasks),
        memory_augmented=len(recalled) > 0,
        recalled_memories=recalled,
    )


@orchestrator_mcp.tool(
    name="distill_conversational_feedback",
    description="Transforms a conversational correction or human rule into an abstracted, de-identified domain best practice and indexes it into vector memory.",
)
def distill_conversational_feedback(
    feedback_text: str,
    domain: str = "general",
) -> Dict[str, Any]:
    """
    Distills human feedback into a generalized best practice or private local rule.
    """
    distiller = BestPracticeDistiller()
    result = distiller.distill_from_conversational_rule(rule_text=feedback_text, domain=domain)
    return result.model_dump()


@orchestrator_mcp.tool(
    name="distill_batch_diff",
    description="Analyzes a batch of human corrections (e.g. from an edited spreadsheet or table) to extract generalized classification rules and update vector memory.",
)
def distill_batch_diff(
    batch_diff_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyzes draft vs final human corrections and distills reusable heuristics.
    """
    distiller = BestPracticeDistiller()
    diff_input = BatchDiffInput(**batch_diff_payload)
    result = distiller.distill_from_batch_diff(diff_input)
    return result.model_dump()


if __name__ == "__main__":
    orchestrator_mcp.run(transport="stdio", show_banner=False)

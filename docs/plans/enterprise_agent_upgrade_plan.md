# Implementation Plan: Sovereign Enterprise Agent Platform & Self-Refining Engine

- **Status**: IN_PROGRESS
- **Target Repository**: `devalees/ai_system_template`
- **Architectural Paradigm**: **Sovereign Autonomous AI Agent Platform (100% Standalone & Portable)**
- **Creation Date**: 2026-09-13
- **Primary References**:
  - Active Plan: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
  - Agent Team Specification: [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md)
  - System Overview: [`docs/ai_wiki/index.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/index.md)
  - Architecture Reference: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)

---

## 1. Executive Summary & Objective

The objective of this plan is to establish the Hermes Agent runtime as a **Sovereign, Enterprise-Grade Autonomous AI Agent Platform** that is **100% independent, portable, and standalone**.

### The Sovereign Architecture
The system operates as a self-contained AI intelligence package holding its own profiles, tool capabilities, embedded vector memory, observability, and evaluation benchmarks:

```
+---------------------------------------------------------------------+
|                     Sovereign Agent Platform                        |
|                     (Hermes / Standalone Agent)                     |
|                                                                     |
|  • 5 Calibrated Specialist Profiles                                 |
|  • Embedded Vector Memory (sqlite-vec in memory.db)                 |
|  • Internal FastMCP Tool Ecosystem                                  |
|  • Independent Golden Benchmark Evaluation Suite (pytest)           |
|  • Knowledge Portability CLI (export / import)                      |
+---------------------------------------------------------------------+
                                  ▲
                                  │ OpenTelemetry
+---------------------------------▼-----------------------------------+
|  Langfuse Dashboard (Standalone Container :3100)                    |
|  - Visual Trace Trees, Step Latencies & Real-Time Token Costs       |
+---------------------------------------------------------------------+
```

### Key Independence Guarantees
- **Portability**: The entire `agent_service/` directory can be lifted and plugged into any external application (FastAPI, Go, Next.js, Express) or executed as a standalone CLI with **zero code modifications**.
- **Swappability**: You can swap Hermes for another agent engine (e.g. LangGraph, CrewAI, AutoGen) inside `agent_service/` without altering client-facing protocols.
- **Zero Database Dependency**: The agent's memory lives in **`sqlite-vec`** (`agent_service/data/memory.db`), completely in-process with zero external database servers.

---

## 2. The 6 Sovereign Pillars

1. **Embedded Sovereign Semantic Memory (`sqlite-vec`)**: In-process vector database inside `agent_service/data/memory.db`. Zero network latency, zero external DB dependencies, and 100% portable with the agent folder.
2. **Model Context Protocol (MCP) Standardized Tooling**: All agent tools run as native FastMCP servers inside `agent_service/mcp/`, communicating via JSON-RPC.
3. **Glass-Box Observability & Tracing (Langfuse)**: Independent Docker container (`ghcr.io/langfuse/langfuse:2`) on port 3100 capturing turn-by-turn thought streams, latency waterfalls, and token pricing.
4. **Schema-Strict Tool Contracts & Mid-Flight Error Recovery**: Pydantic input/output models with automatic error reflection and anti-loop circuit breakers.
5. **Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)**: Automated test harness running directly against the agent runtime (`pytest agent_service/evals/`) standalone.
6. **Cross-Project Knowledge Portability**: Clean separation between generalized procedural wisdom (exportable to new projects) and project-local data.

---

## 3. Comparison Matrix: Legacy Architecture vs. Sovereign Architecture

| Dimension | Legacy Architecture | Sovereign Architecture (Target) | Operational Impact |
| :--- | :--- | :--- | :--- |
| **1. Memory & Knowledge** | **Ephemeral & Session-Bound**<br>• Agents forget past solutions once a task concludes.<br>• Identical problems require full exploration from scratch. | **Embedded Sovereign Memory (`sqlite-vec`)**<br>• `agent_service/data/memory.db` stores vector embeddings inside the agent container.<br>• Agents retrieve top-2 relevant past solutions before turn 1. | **Transformative**<br>• 100% portable with the `agent_service` folder.<br>• Drops average task completion latency by 50–70%. |
| **2. Tooling & Integrations** | **Bespoke CLI Scripts**<br>• Every capability required custom argparse scripts.<br>• Heavy terminal subprocess overhead. | **Universal FastMCP (Model Context Protocol)**<br>• Standardized FastMCP servers inside `agent_service/mcp/`.<br>• Native in-process JSON-RPC execution. | **High**<br>• Standardized across all profiles.<br>• Plug-and-play tool additions. |
| **3. Monitoring & Observability** | **Black-Box Cost Estimates**<br>• Coarse daily token counters.<br>• Cannot visualize turn-by-turn thought trees or per-tool latencies. | **Standalone Glass-Box Tracing (Langfuse :3100)**<br>• Independent Docker service.<br>• Interactive visual trace trees: prompts, reasoning thoughts, tool execution, token costs. | **Transformative**<br>• Complete visibility into agent reasoning.<br>• True production LLMOps. |
| **4. Error Recovery & Self-Correction** | **Late-Stage Gate**<br>• Errors only surfaced at the end of execution.<br>• Fragile raw stderr strings. | **Multi-Tiered Self-Healing**<br>• Strict Pydantic input/output schemas at tool boundaries.<br>• Automatic mid-flight retry with structured error injection.<br>• Anti-loop circuit breaker. | **High**<br>• Prevents tool hallucination.<br>• Catches syntax mistakes in-flight. |
| **5. Continuous Improvement (Evals)** | **Ad-Hoc Manual Prompting**<br>• Tweaking prompts based on guesswork.<br>• No regression test harness. | **Independent Golden Benchmark Suite**<br>• Located in `agent_service/evals/`.<br>• Automated suite of 25+ real-world domain scenarios executed via `pytest`. | **Transformative**<br>• Replaces prompt guesswork with quantitative software engineering.<br>• Verifies model upgrades quantitatively. |
| **6. Cross-Project Portability** | **Siloed & Trapped**<br>• Capabilities trapped in bespoke configurations.<br>• Difficult to export without data contamination. | **Sovereign Package Portability**<br>• The entire `agent_service/` directory is an independent Git repository/submodule.<br>• Export/Import CLI for procedural knowledge. | **Transformative**<br>• Compounding returns across software ventures.<br>• Zero risk of data cross-contamination. |

---

## 4. Phased Implementation Roadmap

```
Phase 36: Clean Slate & Embedded Sovereign Memory (Milestone 1)
  ├── Step 0: Clean-Slate Decoupling & Pure Standalone Hermes Provisioning [COMPLETED]
  ├── Step 1: Install sqlite-vec in agent_service container runtime
  ├── Step 2: Implement agent_service/memory/vector_store.py (memory.db)
  ├── Step 3: Wire automated semantic recall into agent pre-flight loop
  └── Step 4: Verify in-process semantic recall with zero external dependencies

Phase 37: Standalone Observability & Glass-Box Tracing (Milestone 3)
  ├── Step 1: Add independent Langfuse service to agent_service/docker-compose.yml (:3100)
  ├── Step 2: Implement OpenTelemetry interceptor in agent_service/telemetry/tracer.py
  ├── Step 3: Verify visual trace waterfalls, token costs, and per-tool latencies
  └── Step 4: Verify standalone dashboard access

Phase 38: Standardized Tooling, Self-Correction & Profile Refactoring (Milestones 2 & 4)
  ├── Step 1: Implement FastMCP server in agent_service/mcp/system_tools_server.py
  ├── Step 2: Refactor the 5 profiles from CLI scripts to native MCP tools
  ├── Step 3: Implement Tiered Risk-Based QA review (Deterministic Tier 1 vs Conditional Tier 3)
  ├── Step 4: Add Pydantic input/output validation to all MCP tools
  └── Step 5: Implement mid-flight error reflection and loop circuit breakers

Phase 39: Independent Golden Benchmark Evaluation Suite (Milestone 5)
  ├── Step 1: Scaffold agent_service/evals/ test harness with pytest
  ├── Step 2: Author 25 deterministic golden test cases across the 5 agent roles
  ├── Step 3: Implement `./scripts/run_agent_evals.sh` CLI runner
  └── Step 4: Establish automated benchmark verification

Phase 40: Sovereign Package Portability & Knowledge CLI (Milestone 6)
  ├── Step 1: Structure agent_service/ as a standalone, modular package
  ├── Step 2: Implement agent_service/memory/cli.py (export/import)
  ├── Step 3: Verify dropping agent_service into a clean standalone test environment
  └── Step 4: Document Cross-Project Portability standard in docs/ai_wiki/
```

---

## 5. Verification & Success Criteria

1. **Total Sovereignty**:
   - `agent_service/` can be started, executed, and benchmarked standalone with zero external dependencies.
2. **Memory Recall**:
   - Repeat task prompt resolves in **1 turn instead of 4 turns**, cutting task duration by > 50% using `memory.db`.
3. **Observability**:
   - Every agent task generates an active Langfuse trace URL visible in `http://localhost:3100`.
4. **Tool Safety**:
   - Invalid tool arguments trigger instant Pydantic self-correction without crashes.
5. **Benchmark Score**:
   - Pytest evals pass at >= 90% across all 25 golden test cases in under 3 minutes.
6. **Cross-Project Portability**:
   - `python -m agent_service.memory.cli export --scope generalized` outputs a clean, PII-free JSONL file that successfully imports into a fresh database with 100% vector search recall.

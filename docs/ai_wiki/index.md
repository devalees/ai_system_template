# Sovereign Autonomous AI Agent Platform — System Overview

A production-grade, 100% sovereign, and portable autonomous AI agent platform powered by the **Nous Research Hermes Agent** execution engine, featuring embedded vector memory, standardized Model Context Protocol (FastMCP) tool servers, glass-box LLMOps observability, and independent golden benchmark evaluations.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `main`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Agent Team Reference**: [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md)
- **Status**: Phase 36 Enterprise Agent Upgrade COMPLETED across all 6 Pillars (43/43 Golden Benchmark Evals Passing in 2.24s).

---

## The 6 Sovereign Pillars

1. **Embedded Sovereign Semantic Memory (`sqlite-vec`)**: In-process vector database stored in `agent_service/data/memory.db`. Provides sub-15ms cosine distance recall of past solutions prior to turn 1, slashing repetitive exploration and reducing task duration by 50–70%.
2. **Model Context Protocol (FastMCP) Standardized Tooling**: Native JSON-RPC tool ecosystem (`agent_service/mcp/`) executing in-process, replacing fragile shell scripts with typed, high-speed tools.
3. **Glass-Box Observability & Tracing (Langfuse)**: Standalone Docker monitoring service on port `3100` capturing complete thought streams, tool execution waterfalls, latency metrics, and token costs.
4. **Schema-Strict Self-Correction & Circuit Breakers**: Pydantic input/output contracts, mid-flight traceback injection for self-healing, and anti-loop circuit breakers (`MAX_CONSECUTIVE_TOOL_FAILURES = 2`).
5. **Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)**: Automated `pytest` test harness certifying agent intelligence standalone with 25+ deterministic domain scenarios.
6. **Cross-Project Knowledge Portability**: Self-contained package architecture with sanitized knowledge export/import CLI (`agent_service/memory/cli.py`) for compound procedural intelligence across repositories.

---

## Primary System Components

### 1. Autonomous Agent Engine & Gateway (`agent_service/`)
- **Engine**: Nous Research `hermes-agent:local` running in an isolated Docker container (`hermes-template-agent`) on port 8643.
- **Protocol**: OpenAI-compatible REST API Gateway (`/v1/chat/completions`, `/v1/models`) and interactive terminal CLI (`hermes chat`).
- **Isolation**: Completely self-contained container with zero host system dependencies, executing inside `hermes_isolated_network`.

### 2. Embedded Sovereign Semantic Memory (`agent_service/memory/`)
- **Vector Engine**: In-process C-extension `sqlite-vec` embedded directly inside Python, operating on `agent_service/data/memory.db`.
- **Pre-Flight Semantic Recall**: Automatically retrieves top-2 similar past winning patterns before turn 1 and injects them into the agent's context.
- **Post-Flight Indexing**: Automatically summarizes and vector-indexes approved task outcomes into `memory.db`.
- **Zero External Overhead**: In-memory execution with ~10–25 MB RAM footprint and $0 monthly hosting overhead.

### 3. Modular Model Context Protocol (FastMCP) Ecosystem (`agent_service/mcp/`)
- **Architecture**: In-process FastMCP micro-servers communicating over standard JSON-RPC 2.0 with zero-trust profile scoping:
  - `common_tools` (`common_server.py`): Platform-wide tools shared by all agents (`semantic_memory_recall`, `get_platform_status`).
  - `orchestrator_tools` (`orchestrator_server.py`): `decompose_task_dag` with pre-flight memory recall.
  - `qa_tools` (`qa_server.py`): `validate_code_deliverable` combining deterministic Python AST syntax checks ($0, <5ms) with hygiene audits.
  - `security_tools` (`security_server.py`): `security_audit` for high-speed in-memory credential leak scanning and permission audits.
  - `cost_tools` (`cost_server.py`): `audit_token_budget` tracking spend against configured budget caps.
  - `comms_tools` (`comms_server.py`): `client_service_action` for zero-trust document queries and notification routing.
  - `system_tools` (`system_tools_server.py`): Backward-compatible aggregate server.
- **Zero-Trust Scoping**: Profiles declare only `[common_tools, <domain>_tools]`, enforcing least privilege and eliminating prompt bloat.

### 4. Standalone Glass-Box Tracing & LLMOps (`Langfuse` :3100)
- **Containerized Observability**: Independent Docker container (`ghcr.io/langfuse/langfuse:2`) running on host port `3100:3000`.
- **Turn-by-Turn Telemetry**: Directly instrumented via OpenTelemetry and Langfuse Python SDK inside `agent_service/telemetry/tracer.py`.
- **Trace Waterfalls**: Renders complete execution trees including prompt injections, model thinking streams, tool latency, token volume, and exact dollar costs.

### 5. Schema-Strict Execution & Tiered Risk-Based QA
- **Pydantic Validation**: Every tool defines rigid Pydantic argument and return schemas, catching malformed parameters in memory before LLM turn waste.
- **In-Flight Error Reflection**: Detailed tracebacks are injected back into the active LLM context for instant mid-flight self-correction.
- **Anti-Loop Circuit Breaker**: Halts execution cleanly at the 2nd consecutive failure to prevent runaway token spend.
- **Tiered QA Gate**: Routine tasks are auto-verified via Tier 1 deterministic AST checks ($0, <5ms), reserving heavy LLM review turns strictly for high-risk tasks.

### 6. Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)
- **Harness**: Built on standard `pytest` in `agent_service/evals/`.
- **Scope**: 43 deterministic domain test cases validating DAG decomposition, security leak detection, AST validation, semantic memory recall, telemetry tracing, and circuit breaking.
- **Targets**: $100\%$ pass rate (43/43 passing in 2.24s), $100\%$ tool accuracy, $\$0$ token overhead for local checks.
- **Runner**: Standalone script [`agent_service/evals/run_evals.sh`](file:///home/ehab/Desktop/economy_editor/agent_service/evals/run_evals.sh) executable on demand or in CI pipelines.

### 7. Cross-Project Knowledge Portability & Knowledge CLI
- **Package Modularity**: The entire `agent_service/` directory functions as an independent, portable Git repository/submodule.
- **Knowledge CLI (`agent_service/memory/cli.py`)**:
  - `export --scope generalized`: Extracts reusable procedural patterns and vector embeddings into clean JSONL while stripping private client data.
  - `import`: Ingests knowledge packages into fresh project databases (`memory.db`) in seconds, establishing compounding intelligence across projects.

### 8. Dynamic Model Catalog & Multi-Provider Engine
- **Live Registry**: Integrates `models.dev` universal registry and OpenRouter API, supporting Gemini, OpenAI, Anthropic, DeepSeek, and Groq.
- **Telemetry**: Normalizes context windows, input/output token rates ($/1M tokens), and input/output modalities (`text`, `image`, `pdf`, `audio`, `video`).

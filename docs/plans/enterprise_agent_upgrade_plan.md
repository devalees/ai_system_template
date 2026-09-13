# Implementation Plan: Enterprise Agent Upgrade & Self-Refining Platform

- **Status**: PENDING REVIEW <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Target Repository**: `devalees/ai_system_template`
- **Creation Date**: 2026-09-13
- **Primary References**:
  - Active Plan: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
  - Agent Team Specification: [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md)
  - System Overview: [`docs/ai_wiki/index.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/index.md)
  - Architecture Reference: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)

---

## 1. Executive Summary & Objective

The objective of this plan is to transform the existing Hermes Agent runtime and Django backend from an **ephemeral, script-bound agent prototype** into a **self-refining, high-velocity enterprise platform**. 

### The Core Problem (Latency & Amnesia)
In the current setup, Hermes Agent suffers from two operational bottlenecks:
1. **Amnesia (Lack of Long-Term Memory)**: Because agents start every task with zero historical context, they must spend multiple slow LLM turns exploring the environment, querying files, or guessing parameters.
2. **Black-Box Execution**: When an agent takes 40+ seconds or chooses a sub-optimal path, there is no real-time telemetry to see which specific tool call or prompt caused the latency.

### The Solution: The 5 Enterprise Pillars
By introducing:
1. **Institutional Semantic Memory (`pgvector`)** within our existing PostgreSQL 16 database.
2. **Model Context Protocol (MCP)** standardized external tooling.
3. **Glass-Box Tracing & Observability (Langfuse)** in Docker.
4. **Schema-Strict Tool Contracts & Mid-Flight Error Recovery**.
5. **Golden Benchmark Evaluation Suite (`tests/evals/`) & Closed-Loop Improvement Flywheel**.

The agents gain instant recall of prior successful solutions (slashing turn count and latency), complete execution transparency, and a rigorous test harness where every operational failure becomes a permanent test case that prevents regressions.

---

## 2. Comparison Matrix: Current State vs. Post-Implementation

| Dimension | Current State (Now) | Post-Implementation (Target) | Operational Impact |
| :--- | :--- | :--- | :--- |
| **1. Memory & Knowledge (Adaptation)** | **Ephemeral & Session-Bound**<br>• Agents forget past solutions once a task concludes.<br>• Identical problems require full exploration from scratch each time.<br>• Client document search is purely relational metadata, lacking semantic similarity. | **Institutional Semantic Memory (`pgvector`)**<br>• PostgreSQL 16 `pgvector` stores vector embeddings of verified task solutions, client guidelines, and code patterns.<br>• Agents retrieve top-3 relevant past solutions before the first turn.<br>• Semantic search across all client documents in `apps.media`. | **Transformative**<br>• Drastically cuts token count.<br>• Drops average task completion latency by 50–70%. |
| **2. Tooling & Integrations** | **Bespoke CLI Scripts**<br>• Every capability requires a custom Python argparse script in `skills/<name>/run.py`.<br>• Manual symlinking and profile YAML editing for each tool.<br>• Difficult to connect external SaaS (GitHub, Postgres, Slack, Google Drive). | **Universal MCP (Model Context Protocol)**<br>• Hermes runtime connects to standardized MCP servers over JSON-RPC.<br>• Any official or community MCP server plugs in immediately with zero bespoke wrapper code.<br>• Dynamic tool discovery and schema generation. | **High**<br>• Decouples tool development from agent code.<br>• Instant access to hundreds of enterprise MCP servers. |
| **3. Monitoring & Observability** | **Black-Box Cost Totals**<br>• We track high-level daily token totals in `SpendReport` and model CRUD diffs in `ActivityLog`.<br>• Cannot visualize turn-by-turn agent thought process, tool arguments, or per-span latency bottlenecks. | **Glass-Box Waterfall Tracing (Langfuse)**<br>• Lightweight Langfuse Docker container linked to the stack.<br>• Interactive visual trace trees: prompt injection, LLM thinking time, tool execution duration, token pricing per turn.<br>• 1-click filtering: "Tasks with latency > 15s" or "Tasks with tool errors". | **Transformative**<br>• Instant debugging of agent stalls.<br>• Complete auditability for enterprise compliance. |
| **4. Error Recovery & Self-Correction** | **Late-Stage Review Gate**<br>• Quality control happens predominantly at the end of the pipeline when `qa_auditor` inspects the final output files.<br>• Sub-step tool failures rely on raw CLI stderr. | **Multi-Tiered Self-Healing**<br>• Strict Pydantic input/output schemas at tool boundaries.<br>• Automatic mid-flight retry with explicit error explanation injected into the context.<br>• Circuit breakers abort runaway tool loops before consuming token budgets. | **High**<br>• Prevents tool hallucination.<br>• Catches syntax and argument mistakes before wasting turns. |
| **5. Continuous Improvement Cycle (The Flywheel)** | **Ad-Hoc Manual Tweaking**<br>• Improving an agent means guessing changes to `SOUL.md`.<br>• No automated way to verify if adjusting a prompt for one problem broke another capability. | **Closed-Loop Engineering (Golden Evals)**<br>• Automated benchmark suite of 25+ real-world domain scenarios executed via `pytest`.<br>• Clear quantitative score (e.g., "Pass Rate: 92%, Avg Cost: $0.03").<br>• Operational failures convert into new test cases in minutes. | **Transformative**<br>• Replaces prompt guesswork with data-driven software engineering.<br>• Zero regression risk when switching models. |

---

## 3. High-Level Architecture & Data Flow

```mermaid
flowchart TD
    subgraph UI ["User & Frontend (React 3000)"]
        A["User Task Intake / AI Studio"] --> B["Django REST API Gateway (:8000)"]
    end

    subgraph Backend ["Django Backend Platform (apps.*)"]
        B --> C["Task Registry (AgentTask)"]
        C --> D["Memory Engine (apps.memory with pgvector)"]
        D -->|Retrieve Relevant Prior Solutions| E["Asynchronous Dispatcher (Celery)"]
        C -->|On QA Approval| D
    end

    subgraph AgentCore ["Hermes Agent Engine (:8643)"]
        E --> F["Profile Executor (orchestrator / specialist)"]
        F --> G["MCP Client Adapter (Model Context Protocol)"]
        G --> H["Standard MCP Servers (Postgres / FS / Web / GitHub)"]
        F --> I["Observability Interceptor (OpenTelemetry / Langfuse SDK)"]
    end

    subgraph LLMOps ["Observability & Telemetry"]
        I --> J["Langfuse Dashboard (Docker :3100)"]
        J -->|Export Failure Trajectories| K["Golden Eval Benchmark Suite (tests/evals/)"]
        K -->|Prompt & Few-Shot Refinements| F
    end

    subgraph Database ["PostgreSQL 16 Engine"]
        D --- L[("PostgreSQL 16 + pgvector extension")]
    end
```

---

## 4. Detailed Specification Across the 5 Milestones

### Milestone 1: Institutional Semantic Memory (`pgvector` & `apps.memory`)

#### 1.1 Objectives
- Eliminate agent amnesia and slash cold-start task latency by equipping PostgreSQL with semantic vector search.
- Enable agents to automatically recall how similar problems were previously solved.

#### 1.2 Technical Plan
- **Database Extension**: Add `vector` extension to `django-template-db` (PostgreSQL 16) via Django migration.
- **New Django Application**: Create `backend/apps/memory/`:
  - `MemoryEntry` model:
    - `id`: UUIDv4
    - `organization`: ForeignKey (`apps.tenants.Organization`)
    - `category`: Choice (`task_solution`, `client_preference`, `system_pattern`, `document_chunk`)
    - `title`: CharField
    - `content`: TextField (the solution summary, code snippet, or rule)
    - `embedding`: VectorField (dimensions matching embedding model: e.g. 768 for Gemini, 1536 for OpenAI/OpenRouter)
    - `metadata`: JSONField (task ID, author profile, quality score)
    - `created_at` / `updated_at`: Standard timestamps
  - `MemoryService`:
    - `store_solution(task, solution_summary)`: Generates embedding and saves record.
    - `search_relevant(query_text, category, top_k=3, threshold=0.75)`: Executes cosine distance search `<->` in PostgreSQL.
- **Automated Lifecycle Signal**:
  - In `apps.integration.signals`, hook into `AgentTask.status == 'completed'`. When `qa_auditor` approves a task with score >= 85, automatically summarize the successful approach and persist it into `MemoryEntry`.
- **Hermes Profile Skill**:
  - Expose `agent_service/skills/recall_memory/` allowing any agent profile to query `POST /api/v1/memory/recall/` or auto-inject relevant memories during task initialization.

#### 1.3 Key Deliverables
- [ ] Database migration enabling `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Model `backend/apps/memory/models.py` (`MemoryEntry`)
- [ ] Service `backend/apps/memory/services.py` with vector similarity search
- [ ] API endpoints: `GET /api/v1/memory/`, `POST /api/v1/memory/recall/`
- [ ] Automated ingestion signal on QA verdict approval

---

### Milestone 2: Standardized MCP (Model Context Protocol) Integration

#### 2.1 Objectives
- Decouple agent capabilities from brittle, one-off Python CLI scripts.
- Allow Hermes profiles to dynamically invoke standard MCP servers (PostgreSQL, Filesystem, GitHub, Fetch/Web, REST APIs) over JSON-RPC.

#### 2.2 Technical Plan
- **Hermes MCP Client Adapter**:
  - Install `mcp` Python SDK in `agent_service/`.
  - Create a central MCP manager `agent_service/mcp/client_manager.py` that reads declared MCP servers from `agent_service/profiles/<name>/config.yaml`.
  - Standard configuration syntax:
    ```yaml
    mcp_servers:
      postgres:
        command: "mcp-server-postgres"
        env:
          DATABASE_URL: "postgresql://user:pass@django-template-db:5432/db"
      filesystem:
        command: "mcp-server-filesystem"
        args: ["/app/workspace"]
    ```
- **Tool Schema Normalization**:
  - Automatically convert MCP tool descriptions into JSON-schema function definitions exposed directly to the Hermes LLM context.
- **Least-Privilege Scoping**:
  - Profile-specific MCP permissions (e.g. `security_guard` gets read-only filesystem MCP; `orchestrator` gets task decomposition MCP).

#### 2.3 Key Deliverables
- [ ] MCP client bridge in `agent_service/core/mcp_client.py`
- [ ] Configuration schema in `agent_service/profiles/<profile>/config.yaml`
- [ ] First standardized MCP server deployment (PostgreSQL & Workspace Filesystem)

---

### Milestone 3: Glass-Box LLMOps Observability & Waterfall Tracing (Langfuse)

#### 3.1 Objectives
- Provide complete visual transparency into agent reasoning, token costs, and tool execution latency.
- Enable 1-click inspection of slow or failed agent turns.

#### 3.2 Technical Plan
- **Container Infrastructure**:
  - Add lightweight Langfuse service to root `docker-compose.yml`:
    - Image: `ghcr.io/langfuse/langfuse:2`
    - Port: `3100:3000`
    - Connects to existing PostgreSQL 16 database under a separate database/schema (`langfuse`).
- **Telemetry Interceptor**:
  - Configure `agent_service/` with `langfuse` Python SDK / OpenTelemetry.
  - Automatically wrap every agent invocation (`hermes -p <profile>` or gateway call) in a Langfuse Trace:
    - **Trace**: Root Task UUID, requesting user, organization ID.
    - **Generation Spans**: LLM system prompt, user prompt, reasoning thinking blocks, output tokens, cost ($ USD).
    - **Tool Spans**: Tool name, arguments passed, execution duration (ms), return payload, error status.
- **Frontend / Admin Integration**:
  - Add a direct link in the Django Admin and React Frontend TopBar to open the Langfuse dashboard (`http://localhost:3100`).
  - Add trace link directly on `AgentTaskAdmin` in Django (`View Trace in Langfuse ↗`).

#### 3.3 Key Deliverables
- [ ] Docker compose configuration for Langfuse
- [ ] Hermes telemetry wrapper in `agent_service/telemetry/tracer.py`
- [ ] Ingestion of turn tokens, latencies, and costs into Langfuse
- [ ] Admin & TopBar direct shortcuts to trace views

---

### Milestone 4: Schema-Strict Execution & Mid-Flight Self-Correction

#### 4.1 Objectives
- Stop agents from hallucinating tool arguments or looping endlessly on syntax errors.
- Ensure every tool invocation is strictly validated against Pydantic schemas before running.

#### 4.2 Technical Plan
- **Pydantic Tool Input/Output Contracts**:
  - All tools define strict input models inheriting `pydantic.BaseModel`.
  - If the LLM generates an invalid payload (e.g. string instead of int, missing required field), execution is halted immediately before hitting system APIs.
- **In-Flight Error Reflection**:
  - Rather than terminating the task on failure, the specific Pydantic validation error or API exception is cleanly formatted and injected back into the LLM conversation:
    `"Error: Tool 'client_budget_check' failed: Field 'client_id' must be a valid UUID. You provided 'abc'. Please correct your input."`
- **Strict Circuit Breaker**:
  - If an agent repeats the same invalid tool call twice, the loop is broken immediately and escalated to `qa_auditor` / human review, preventing token drain.

#### 4.3 Key Deliverables
- [ ] Pydantic validation middleware in tool executor
- [ ] Mid-flight error reflection prompt formatter
- [ ] Anti-loop circuit breaker (max 2 consecutive identical failures)

---

### Milestone 5: Golden Benchmark Evaluation Suite & Self-Healing Flywheel

#### 5.1 Objectives
- Establish an automated, objective testing pipeline for agent intelligence and task success.
- Turn every production failure into a deterministic test case to prevent future regressions.

#### 5.2 Technical Plan
- **Golden Evaluation Test Harness (`backend/tests/evals/`)**:
  - Create 25+ curated, reproducible test cases covering key domain tasks:
    1. `test_orchestrator_decomposes_complex_billing_request`
    2. `test_security_guard_catches_exposed_rsa_key_in_diff`
    3. `test_cost_controller_enforces_budget_ceiling`
    4. `test_qa_auditor_rejects_todo_placeholders`
    5. `test_comms_agent_respects_client_ai_disabled_flag`
- **Automated CLI Benchmark Runner**:
  - Add management command `python manage.py run_evals --profile <name>`
  - Evaluates:
    - **Task Completion Rate** (Target >= 90%)
    - **Tool Correctness** (Target 100%)
    - **Token Efficiency / Cost per Task** (Target <= $0.05)
    - **Total Duration / Latency** (Target <= 15s)
- **The Closed Feedback Loop Workflow**:
  1. Langfuse alerts to a failed task in production.
  2. Developer/Admin copies the scenario into `tests/evals/cases/<case_id>.json`.
  3. Update profile `SOUL.md` or add 1 Few-Shot example.
  4. Run `python manage.py run_evals` — verify pass rate improves.
  5. Deploy with zero risk.

#### 5.3 Key Deliverables
- [ ] Eval dataset directory `backend/tests/evals/datasets/`
- [ ] Pytest runner and assertions in `backend/tests/evals/test_golden_scenarios.py`
- [ ] Django management command `python manage.py run_evals`
- [ ] Documentation guide on converting production errors to eval cases

---

## 5. Phased Implementation Roadmap

```
Phase 36: Foundation & Semantic Memory (Milestone 1)
  ├── Step 1: Add PostgreSQL pgvector extension to database container
  ├── Step 2: Implement apps.memory Django app (MemoryEntry, similarity search)
  ├── Step 3: Wire automated memory storage signal on QA approval
  └── Step 4: Add memory recall endpoint & verify semantic query accuracy

Phase 37: Observability & Glass-Box Tracing (Milestone 3)
  ├── Step 1: Add Langfuse container to docker-compose.yml
  ├── Step 2: Implement OpenTelemetry/Langfuse interceptor in Hermes agent
  ├── Step 3: Verify visual trace waterfalls, token costs, and step latencies
  └── Step 4: Add Django Admin and Frontend TopBar direct trace shortcuts

Phase 38: Standardized Tooling & Self-Correction (Milestones 2 & 4)
  ├── Step 1: Implement MCP client manager in agent_service/
  ├── Step 2: Deploy standard PostgreSQL and Filesystem MCP servers
  ├── Step 3: Implement Pydantic schema validation on all tool calls
  └── Step 4: Add mid-flight error injection and loop circuit breakers

Phase 39: Golden Evaluation Suite & Continuous Improvement Flywheel (Milestone 5)
  ├── Step 1: Scaffold backend/tests/evals/ benchmark harness
  ├── Step 2: Author 25 deterministic golden test cases across the 5 agent roles
  ├── Step 3: Implement `python manage.py run_evals` CLI with pass/fail metrics
  └── Step 4: Document the step-by-step Feedback Loop workflow in docs/ai_wiki/
```

---

## 6. Hardware & Infrastructure Footprint

| Component | Additional Server Needed? | RAM Footprint | CPU Overhead | Monthly Hosting Cost |
| :--- | :--- | :--- | :--- | :--- |
| **`pgvector`** | **No** (Runs in existing PostgreSQL container) | ~20–40 MB | Negligible (indexed `<->` search) | **$0** |
| **MCP Client** | **No** (Runs in existing Hermes container) | ~15–30 MB | Negligible (JSON-RPC) | **$0** |
| **Langfuse** | **No** (Lightweight Docker service) | ~200–350 MB | Low (~1–3% CPU during logging) | **$0** |
| **Golden Evals**| **No** (CLI Pytest command executed on demand)| Transient | Only during benchmark execution | **$0** |
| **TOTAL** | **0 New Servers** | **~250–420 MB RAM** | **Standard Host is more than sufficient** | **$0 Added Cost** |

---

## 7. Verification & Success Criteria

1. **Memory Recall**:
   - Agent presented with a repeat problem completes it in **1 turn instead of 4 turns**, cutting response latency by > 50%.
2. **Observability**:
   - Every agent task generates an active Langfuse trace URL visible directly in Django Admin.
3. **Tool Safety**:
   - Malformed tool inputs trigger instant Pydantic correction without crash or unhandled 500 error.
4. **Benchmark Score**:
   - `python manage.py run_evals` passes at >= 90% across all 25 golden test cases in under 3 minutes.

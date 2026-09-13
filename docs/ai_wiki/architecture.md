# System Architecture: Sovereign Autonomous AI Agent Platform

## 1. Technical Stack & Isolation Architecture

- **Agent Execution Engine**: Nous Research Hermes Agent (`hermes-agent:local`) containerized on port 8643.
- **Embedded Semantic Vector Store**: `sqlite-vec` in `agent_service/data/memory.db` (in-process C-extension; zero external DB server dependency).
- **Tool Protocol**: Model Context Protocol (FastMCP) over in-process JSON-RPC 2.0 (`agent_service/mcp/`).
- **Glass-Box Tracing & LLMOps**: Standalone Langfuse container (`ghcr.io/langfuse/langfuse:2`) on port 3100.
- **Evaluation Harness**: Independent `pytest` benchmark suite (`agent_service/evals/`).
- **Knowledge CLI**: Sanitized procedural knowledge export/import engine (`agent_service/memory/cli.py`).
- **Container Architecture**:
  - Isolated Docker network (`hermes_isolated_network`).
  - Completely self-contained: zero external web framework, zero database servers (PostgreSQL/Redis), zero shared host filesystems.
  - Standardized gateway interface: OpenAI-compatible HTTP REST (`/v1/chat/completions`, `/v1/models`) and interactive terminal CLI (`hermes chat`).

---

## 2. Port Allocation & Containers

| Service | Container Name | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| `hermes` | `hermes-template-agent` | 8643 | 8642 | Hermes Agent Gateway daemon (OpenAI-compatible) |
| `langfuse` | `langfuse-template-observability` | 3100 | 3000 | Standalone Langfuse LLMOps Tracing Dashboard |

---

## 3. Directory Layout

```
economy_editor/
├── agent_service/                   # Sovereign AI Agent Package (100% Portable)
│   ├── docker-compose.yml           # Hermes isolated container definition
│   ├── .env                         # Local environment & LLM provider credentials
│   ├── .env.example                 # Example configuration template
│   ├── profiles/                    # Calibrated Profiles (SOUL.md, config.yaml, profile.yaml)
│   ├── mcp/                         # Internal Model Context Protocol Tool Ecosystem
│   │   ├── common_server.py         # Shared platform tools (semantic_memory_recall, get_platform_status)
│   │   ├── orchestrator_server.py   # Chief of Staff tools (decompose_task_dag)
│   │   ├── qa_server.py             # QA Gatekeeper tools (validate_code_deliverable)
│   │   ├── security_server.py       # Threat Auditor tools (security_audit)
│   │   ├── cost_server.py           # Financial Controller tools (audit_token_budget)
│   │   ├── comms_server.py          # Client Concierge tools (client_service_action)
│   │   ├── system_tools_server.py   # Backward-compatible aggregate FastMCP server
│   │   └── schemas.py               # Pydantic input/output validation schemas
│   ├── memory/                      # Embedded Sovereign Vector Engine (sqlite-vec)
│   │   ├── vector_store.py          # MemoryStore with cosine similarity search (<15ms)
│   │   └── cli.py                   # Knowledge Export & Import CLI (PII-sanitized)
│   ├── data/                        # Persistent Sovereign Storage (memory.db, runtime state)
│   │   └── memory.db                # In-process sqlite-vec database
│   ├── evals/                       # Independent Golden Benchmark Evaluation Suite
│   │   ├── test_golden_evals.py     # 25+ deterministic domain test cases (pytest)
│   │   └── conftest.py              # Standalone pytest fixtures
│   └── telemetry/                   # Glass-Box Observability Hooks
│       └── tracer.py                # OpenTelemetry & Langfuse telemetry interceptor
└── docs/
    ├── ai_wiki/                     # System architecture & documentation wiki
    │   ├── index.md                 # System overview & primary components
    │   └── architecture.md          # Technical architecture & design patterns
    ├── agent_team.md                # Workforce profile specifications
    └── plans/                       # Active implementation plans
        ├── active_plan.md           # Cumulative task tracking & milestones
        └── enterprise_agent_upgrade_plan.md # 6-Pillar upgrade specification
```

---

## 4. The 6 Sovereign Pillars: Deep Architectural Design

### 4.1 Pillar 1: Embedded Sovereign Semantic Memory (`sqlite-vec`)
- **Engine**: In-process C-extension `sqlite-vec` embedded directly inside Python, operating on `agent_service/data/memory.db`.
- **Latency & Footprint**:
  - Memory queries execute in-memory with sub-15ms latency.
  - Footprint is ~10–25 MB RAM with zero external server dependencies ($0/month hosting).
- **Data Schema**:
  - `memory_entries`: `id` (TEXT PK), `category` (TEXT), `title` (TEXT), `content` (TEXT), `scope` (`generalized` vs `project_local`), `metadata_json` (TEXT), `created_at` (TIMESTAMP).
  - `vec_entries`: Virtual vector table indexed via `sqlite-vec` (768 or 1536 dimensions).
- **Pre-Flight Semantic Recall Loop**:
  ```
  [Task Request / User Prompt]
             │
             ▼
  [Pre-Flight Hook: vector_store.recall_similar(task_prompt, top_k=2)]
             │
             ├── In-Process Cosine Distance Search (<15ms)
             ▼
  [Top-2 Proven Past Solutions Injected into Turn 1 System Prompt]
             │
             ▼
  [Agent Solves Task in 1 Turn instead of 4+ Iterations] (50–70% Latency & Token Reduction)
             │
             ▼ (Upon Successful Validation)
  [Post-Flight Hook: vector_store.add_memory(solution_summary)]
  ```

---

### 4.2 Pillar 2: Standardized & Modular Model Context Protocol (FastMCP) Ecosystem
- **Protocol**: Standard JSON-RPC 2.0 over clean stdio transport.
- **Modular Micro-Servers (`agent_service/mcp/`)**:
  - Eliminates monolithic tool clutter, tool distraction, and prompt bloat.
  - Implements strict zero-trust least privilege across 6 focused FastMCP servers:
    1. **`common_tools` (`common_server.py`)**: Platform-wide tools shared by all agents (`semantic_memory_recall`, `get_platform_status`).
    2. **`orchestrator_tools` (`orchestrator_server.py`)**: `decompose_task_dag` with pre-flight semantic memory augmentation.
    3. **`qa_tools` (`qa_server.py`)**: `validate_code_deliverable` with Tier 1 deterministic AST syntax checking ($0, <5ms).
    4. **`security_tools` (`security_server.py`)**: `security_audit` with high-speed regex scanning for leaked secrets and permission violations.
    5. **`cost_tools` (`cost_server.py`)**: `audit_token_budget` with 4-tier milestone alerts.
    6. **`comms_tools` (`comms_server.py`)**: `client_service_action` for zero-trust document queries and notification routing.
- **Zero-Trust Profile Scoping**:
  - Each profile's `profile.yaml` declares only `[common_tools, <specialist>_tools, ...]`.
  - For example, `comms_agent` physically has no access to code validation, terminal, or security tools.

---

### 4.3 Pillar 3: Standalone Glass-Box Tracing & LLMOps (Langfuse :3100)
- **Containerized Observability**: Standalone Langfuse service (`ghcr.io/langfuse/langfuse:2`) running on port `3100:3000`.
- **Telemetry Interceptor (`agent_service/telemetry/tracer.py`)**:
  - Wraps agent inference loops with OpenTelemetry instrumentation:
    - **Trace Root**: Task UUID, active profile name, calibrated reasoning effort.
    - **Generation Spans**: Prompt text, thinking stream, output tokens, latency (ms), and exact dollar cost calculated via catalog token pricing.
    - **Tool Spans**: MCP tool name, validated input arguments, execution duration, and exit status.
  - Renders complete visual trace waterfalls in the Langfuse dashboard.

---

### 4.4 Pillar 4: Schema-Strict Execution & Mid-Flight Self-Correction
- **Pydantic Tool Contracts (`agent_service/mcp/schemas/`)**:
  - Every FastMCP tool defines rigid Pydantic argument and return schemas.
  - Malformed tool invocations are rejected immediately in memory with zero API token spend and zero shell overhead.
- **Mid-Flight Context Reflection**:
  - Structured validation errors are formatted and injected directly into the active LLM context:
    `"Error: Tool 'security_audit' requires 'mode' to be one of ['leaks', 'tenant', 'rbac']. Provided 'all'. Please correct your input."`
  - The agent self-corrects mid-flight without crashing or failing the overall task pipeline.
- **Anti-Loop Circuit Breaker**:
  - Tracks consecutive failed tool attempts. If an agent repeats the same invalid tool invocation twice consecutively (`MAX_CONSECUTIVE_TOOL_FAILURES = 2`), execution aborts cleanly with diagnostic logs.

---

### 4.5 Pillar 5: Tiered Risk-Based Quality Assurance State Machine
Rather than forcing every task through a heavy, expensive 2nd LLM turn with `reasoning: high`, the architecture employs a 3-tier risk-based validation pipeline:

```
[Agent Task Execution]
        │
        ▼
[Tier 1: In-Process AST & Schema Check] ──(Syntax Error)──► [Tier 2: In-Flight Context Injection]
        │                                                                │
        ▼ (Syntax Valid)                                                 ▼ (Max 2 retries)
[Risk & Confidence Gate]                                      [Self-Correction Succeeded?]
        │                                                       ├── Yes ──► (Resume Task)
        ├── High-Risk OR Confidence < 85%                       └── No  ──► [Circuit Breaker: Failed]
        │       │
        │       ▼
        │   [Tier 3: QA Auditor LLM Review (High Reasoning)]
        │           │
        │           ├── Approved ─────────────┐
        │           └── Changes Requested ──┐ │
        │                                   │ │
        └── Low-Risk AND Confidence >= 85%  │ │
                │                           │ │
                ▼ (Direct Auto-Approve)     │ │
        [Task: Completed & Indexed] ◄───────┴─┘
                ▲
                └── [Task: In Progress / Rejected] ◄────────┘
```

---

### 4.6 Pillar 6: Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)
- **Harness**: Built entirely within `agent_service/evals/` and driven by standard `pytest`.
- **Zero External Dependency**: Executes directly against the agent runtime (`pytest agent_service/evals/`) in any environment.
- **25 Deterministic Golden Scenarios**:
  1. `test_orchestrator_decomposes_complex_task`: Validates DAG generation, dependency ordering, and cycle rejection.
  2. `test_security_guard_detects_api_key_leak`: Tests regex detection of OpenAI, OpenRouter, Anthropic, Stripe, and SSH keys.
  3. `test_qa_auditor_rejects_syntax_errors`: Confirms Tier 1 deterministic rejection of invalid Python AST.
  4. `test_memory_recall_returns_correct_prior_pattern`: Validates semantic search accuracy in `memory.db`.
  5. `test_circuit_breaker_halts_infinite_loop`: Ensures runaway tool invocations halt at the 2nd consecutive failure.
- **Quantitative Targets**: $\ge 90\%$ pass rate, $100\%$ tool invocation accuracy, $\le \$0.05$ cost per run, $\le 15$ seconds duration.

---

### 4.7 Pillar 7: Cross-Project Knowledge Portability & Knowledge CLI
- **Sanitized Knowledge Export**:
  ```bash
  python -m agent_service.memory.cli export --scope generalized --output knowledge_seed.jsonl
  ```
  Extracts validated procedural problem-solving patterns and vector embeddings while stripping all private data, proprietary names, and confidential records.
- **Instant Knowledge Import**:
  ```bash
  python -m agent_service.memory.cli import --input knowledge_seed.jsonl
  ```
  Injects procedural wisdom into any new project's `memory.db` in seconds, delivering Day 1 compound intelligence across all software projects.

---

## 5. Hardware, Resource & Infrastructure Footprint

| Component | Dedicated Server? | RAM Footprint | CPU Overhead | Monthly Hosting Cost |
| :--- | :--- | :--- | :--- | :--- |
| **`hermes` Gateway** | In Docker container | ~80–150 MB | Low (idle <1%) | **$0** |
| **`sqlite-vec`** | In-process C extension | ~10–25 MB | Negligible (<15ms queries) | **$0** |
| **FastMCP Tool Server** | In-process JSON-RPC | ~15–30 MB | Negligible | **$0** |
| **Langfuse Dashboard** | Standalone Docker container | ~200–350 MB | Low (~1–3% during logging) | **$0** |
| **Golden Evals** | Transient `pytest` process | Transient | Only during test execution | **$0** |
| **TOTAL** | **0 External Servers** | **~300–550 MB RAM** | **Standard Host is more than sufficient** | **$0 Added Cost** |

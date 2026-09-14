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
│   │   ├── orchestrator_server.py   # Chief of Staff tools (decompose_task_dag, distill_feedback)
│   │   ├── integration_server.py    # Discovery, Dynamic Provisioning & Scoped RBAC API Proxy
│   │   ├── credential_vault.py      # Per-Agent Scoped Credential Vault & Body Sanitizer
│   │   ├── qa_server.py             # QA Gatekeeper tools (validate_code_deliverable)
│   │   ├── security_server.py       # Threat Auditor tools (security_audit)
│   │   ├── cost_server.py           # Financial Controller tools (audit_token_budget)
│   │   ├── system_tools_server.py   # Backward-compatible aggregate FastMCP server
│   │   └── schemas.py               # Pydantic input/output validation schemas
│   ├── memory/                      # Embedded Sovereign Vector Engine (sqlite-vec)
│   │   ├── vector_store.py          # MemoryStore with cosine similarity search (<15ms)
│   │   └── cli.py                   # Knowledge Export & Import CLI (PII-sanitized)
│   ├── sync/                        # Autonomous Cross-Instance Git Knowledge Sync
│   │   ├── knowledge_sync.py        # Central Git Hub sync engine with PAT auth
│   │   └── daemon.py                # Periodic sync daemon & CLI (--once, --interval-hours)
│   ├── learning/                    # Human-in-the-Loop (HITL) Distillation Engine
│   │   ├── distiller.py             # BestPracticeDistiller (de-identification & rule synthesis)
│   │   └── schemas.py               # Diff schemas, distillation inputs & results
│   ├── data/                        # Persistent Sovereign Storage (memory.db, runtime state)
│   │   └── memory.db                # In-process sqlite-vec database
│   ├── evals/                       # Independent Golden Benchmark Evaluation Suite (72 tests)
│   │   ├── run_evals.sh             # Standalone benchmark runner script
│   │   ├── test_golden_scenarios.py # Orchestrator, QA, Security, Cost & Comms benchmarks
│   │   ├── test_integration_server.py# RBAC, Discovery & Provisioning benchmarks
│   │   ├── test_knowledge_sync.py   # Multi-node Git sync benchmarks
│   │   ├── test_learning_distiller.py# HITL diff distillation & de-identification benchmarks
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
    3. **`integration_tools` (`integration_server.py`)**: External system discovery, Day-1 schema indexing, dynamic agent provisioning (`provision_custom_agent`), agent cataloging, and zero-trust authenticated API proxying (`invoke_external_api`, `fetch_company_profile`, `sync_external_records`).
    4. **`qa_tools` (`qa_server.py`)**: `validate_code_deliverable` with Tier 1 deterministic AST syntax checking ($0, <5ms).
    5. **`security_tools` (`security_server.py`)**: `security_audit` with high-speed regex scanning for leaked secrets and permission violations.
    6. **`cost_tools` (`cost_server.py`)**: `audit_token_budget` with 4-tier milestone alerts.
- **Two-Tier Workforce Model & Per-Agent Scoped Credential Vault (`credential_vault.py`)**:
  - **Tier 1 (Core Sovereign Governance)**: `orchestrator`, `security_guard`, `cost_controller`, `qa_auditor`. These profiles are immutable platform invariants with **ZERO external database write access**; they operate purely as internal guardians.
  - **Tier 2 (Dynamic Domain Specialists)**: Pluggable business agents provisioned via JSON manifests (e.g. `procurement_agent`, `radiology_agent`, `billing_agent`). Each domain agent holds its own scoped token and wildcard endpoint RBAC policy, preventing lateral privilege escalation.
  - **Zero Raw Key Exposure**: Secrets reside in `.env` or `agent_service/data/.credentials.json` (`0600`) and are attached in-process; raw keys are never passed into LLM prompt contexts.



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

### 4.6 Pillar 5: Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)
- **Harness**: Built entirely within `agent_service/evals/` and driven by standard `pytest`.
- **Zero External Dependency**: Executes directly against the agent runtime (`pytest agent_service/evals/`) in any environment or container.
- **72 Deterministic Golden Scenarios**:
  1. `test_golden_scenarios.py` (13 tests): Validates DAG generation, dependency ordering, cycle rejection, cost burn milestones, QA AST syntax rejection, security secret scanning, and comms dispatch.
  2. `test_integration_server.py` (12 tests): Validates Tier 1 zero-write governance enforcement, wildcard RBAC, Day-1 external schema discovery, dynamic agent provisioning & deprovisioning, and credential scrubbing.
  3. `test_knowledge_sync.py` (6 tests): Validates PAT URL generation, scope quarantine, secret scrubbing, vector deduplication, skill mounting, and end-to-end multi-node Git sync.
  4. `test_learning_distiller.py` (4 tests): Validates Trial Balance classification diff distillation, conversational rule de-identification, internal routing quarantine, and FastMCP orchestrator tools.
  5. `test_modular_mcp.py` (7 tests): Validates individual FastMCP server tool discovery and zero-trust profile isolation.
  6. `test_qa_pipeline.py` (6 tests): Validates 3-tier QA risk state machine and circuit breakers.
  7. `test_system_tools.py` (8 tests): Validates backward-compatible system tools.
  8. `test_telemetry.py` (5 tests): Validates cost calculations, token generation tracking, and non-blocking Langfuse dispatch.
  9. `test_vector_store.py` (11 tests): Validates `sqlite-vec` cosine similarity ranking, filtering, sanitization, export/import, and deletion.
- **Quantitative Targets**: $100\%$ pass rate (72/72 passing in 2.98s), $100\%$ tool invocation accuracy, $\$0$ token overhead for local checks.
- **Runner**: Standalone shell script [`agent_service/evals/run_evals.sh`](file:///home/ehab/Desktop/economy_editor/agent_service/evals/run_evals.sh).

---

### 4.7 Pillar 6: Cross-Project Knowledge Portability & Knowledge CLI
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

### 4.8 Pillar 7: Autonomous Cross-Instance Knowledge & Skill Synchronization (`agent_service/sync/`)
- **Central Repository**: Synchronizes with remote Git/GitHub repository (`https://github.com/devalees/skills.git`) using fine-grained Personal Access Tokens (`KNOWLEDGE_HUB_AUTH_TOKEN`).
- **Deterministic Delta Push & Pull**:
  - `push_delta()`: Exports local `scope='generalized'` vector memories and vetted `skills/` bundles into the local sync workspace, executes automated PII/secret scrubbing, commits, and pushes to remote Git.
  - `pull_and_merge()`: Pulls latest commits from remote Git, performs in-process cosine distance deduplication ($\ge 0.88$) against local `sqlite-vec`, inserts novel entries, and mounts inbound `SKILL.md` bundles into local runtimes.
- **Tenant Scope Quarantine**: Physical database isolation ensures that `scope='project_local'` records are strictly barred from export queries.
- **Daemon Lifecycle (`agent_service/sync/daemon.py`)**:
  - `--once`: Deterministic one-shot synchronization for cron runners and container startup hooks.
  - `--interval-hours N`: Long-running non-blocking background daemon polling and synchronizing on schedule.

---

### 4.9 Pillar 8: Human-in-the-Loop (HITL) Feedback & Best Practice Distillation Engine (Correction Mechanism — آلية التصحيح)

#### 4.9.1 Architectural Purpose & Problem Statement
- Traditional agent platforms suffer from static prompt degeneration: when an AI model makes a domain classification error (e.g. Misclassifying an overdraft account under Cash instead of Liabilities on a Trial Balance), the error recurs endlessly unless manually patched by human developers in prompt files.
- The **HITL Distillation Engine (`agent_service/learning/`)** establishes an autonomous cognitive reflection loop: whenever a domain expert (accountant, auditor, procurement officer) corrects deliverable diffs or speaks corrections in chat, the platform extracts, de-identifies, abstracts, and vector-indexes the underlying principle permanently into `sqlite-vec`.

#### 4.9.2 The Distillation & De-Identification Lifecycle

```
[Human Domain Correction / Feedback]
  │
  ├── 1. Batch Classification Diff (e.g. Trial Balance edits)
  └── 2. Conversational Feedback ("In our company Acme Corp, we always require 3-way matching")
        │
        ▼
[BestPracticeDistiller (agent_service/learning/distiller.py)]
        │
        ├── Step 1: Corporate Entity Stripping & De-identification
        │     - Removes regex patterns: "In our company...", "At Acme Corp...", "Our policy states..."
        │     - Sanitizes API tokens, employee IDs, email addresses, and private IP addresses.
        │
        ├── Step 2: Scope & Generalization Gatekeeper
        │     ├── Arbitrary Internal Routing? (e.g. "Forward bills to Alice at ext 402")
        │     │     └── Scope: `project_local`, `is_best_practice=False`, Category: `internal_policy`
        │     └── Universal Domain Principle? (e.g. 3-Way Matching, Overdraft classification)
        │           └── Scope: `generalized`, `is_best_practice=True`, Category: `accounting_heuristic`
        │
        ├── Step 3: Semantic Deduplication & Vector Indexing
        │     - Computes normalized vector embeddings via `sqlite-vec`.
        │     - Executes in-process similarity search (`threshold=0.90`).
        │     - Indexes novel best practices into `memory.db` with structured metadata.
        │
        ├── Step 4: Pre-Flight Compound Intelligence (Turn 1 Reuse)
        │     - Next time ANY agent processes a matching task, `recall_similar(top_k=2)`
        │       automatically injects the distilled best practice before Turn 1.
        │
        └── Step 5: Cross-Instance Synchronization (Pillar 7)
              - Local sync engine pushes the generalized best practice to `devalees/skills.git`.
              - All distributed company instances inherit the human correction immediately.
```

#### 4.9.3 FastMCP Orchestrator Integration
The Orchestrator MCP server exposes two typed tools for the Chief of Staff:
1. `distill_conversational_feedback(rule_text, domain)`:
   - Takes conversational user directives, extracts the abstract best practice, strips corporate entity names, and returns structured distillation results.
2. `distill_batch_diff(diff_items, deliverable_type, context)`:
   - Takes tabular diffs (e.g. `[{"item_label": "Overdraft Account", "ai_original_value": "Cash", "human_corrected_value": "Current Liabilities", "field": "Account Group"}]`), detects domain heuristic patterns, and writes deduplicated rules into `memory.db`.

---

## 5. Hardware, Resource & Infrastructure Footprint

| Component | Dedicated Server? | RAM Footprint | CPU Overhead | Monthly Hosting Cost |
| :--- | :--- | :--- | :--- | :--- |
| **`hermes` Gateway** | In Docker container | ~80–150 MB | Low (idle <1%) | **$0** |
| **`sqlite-vec` Memory** | In-process C extension | ~10–25 MB | Negligible (<15ms queries) | **$0** |
| **FastMCP Modular Servers** | In-process JSON-RPC | ~15–30 MB | Negligible | **$0** |
| **Knowledge Sync Daemon** | In-process / Background | ~10–20 MB | Transient (Git push/pull) | **$0** |
| **HITL Distillation Engine** | In-process Python/Regex | ~5–10 MB | Negligible (<5ms diff parse) | **$0** |
| **Langfuse Dashboard** | Standalone Docker container | ~200–350 MB | Low (~1–3% during logging) | **$0** |
| **Golden Evals Suite** | Transient `pytest` process | Transient | Only during test execution | **$0** |
| **TOTAL** | **0 External Servers** | **~320–580 MB RAM** | **Standard Host is more than sufficient** | **$0 Added Cost** |

---

## 6. Enterprise Tenancy, Registration Gating & Provisioning Architecture

### 6.1 Multi-Tenant Hierarchy & `Company` Entity
- **Root Tenant Entity (`Company`)**:
  - The `Company` model (`modules/base/identity_rbac/models.py`) represents the isolated enterprise organization.
  - Inherits from `Base, UUIDPrimaryKeyMixin, TimestampMixin, AuditActorMixin, ExtensibleModelMixin, SoftDeleteMixin, ArchivableMixin`.
  - Intentionally does NOT inherit `TenantMixin` because `Company` is the root tenant boundary itself.
- **Registration Gating Policy (`allow_registration: bool = False`)**:
  - **Self-Registration (`POST /api/v1/identity_rbac/auth/register`)**: Requires target `company_id` to exist and hold `allow_registration == True`. Attempts to register against organizations where `allow_registration == False` are rejected with `403 Forbidden`.
  - **Internal Provisioning (`POST /api/v1/identity_rbac/users`)**: Authenticated administrators and superusers can provision employee and AI agent accounts internally at any time, completely bypassing `allow_registration`.
- **Company Administration API (`/api/v1/identity_rbac/companies`)**:
  - CRUD endpoints for managing tenant organizations, updating configuration, and toggling `allow_registration` dynamically.

### 6.2 Interactive Database Installer & Setup CLI (`backend/setup_database.py`)
- **Asynchronous CLI Installer**:
  - Drops and recreates clean PostgreSQL schemas (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`).
  - Discovers and loads all module declarative models in topological DAG order.
  - Seeds ISO foundational master data (Currencies, Countries, UoMs, Tax Types).
  - Prompts interactively with input validation:
    - Username: 3–50 chars, alphanumeric + underscores/hyphens, strictly no whitespace.
    - Password: Masked input with confirmation, minimum 8 characters.
    - Email: Standard RFC email format.
    - Organization: Primary company name and registration toggle.
  - Creates the primary tenant `Company` and provisions the Super Administrator (`is_superuser=True`) with global universal access across all current and future modules.
  - Automatically exports freshly synchronized `openapi.json`, `postman_collection.json`, and `postman_environment.json`.

---

### 6.3 Modular Deactivation & Polymorphic Linkage Standard (معيار إلغاء التفعيل والربط متعدد الأشكال)

#### 6.3.1 Non-Destructive Lifecycle Policy (عدم حذف الجداول أو السجلات)
- **Zero Schema Purging**: The platform strictly forbids executing destructive DDL statements (`DROP TABLE`, `DROP COLUMN`) or purging operational databases when a functional business module is uninstalled or deactivated.
- **Dynamic Route Detachment**: Deactivating a module toggles its manifest activation flag within the Module Registry and gracefully revokes its registered endpoints from the FastAPI routing table in-memory without breaking foreign tables.
- **Regulatory Audit Compliance**: Financial, tax, accounting, and compliance records belonging to a deactivated module are permanently preserved with complete historical audit actor timestamps (`created_at`, `created_by_id`, `updated_at`, `updated_by_id`).

#### 6.3.2 Polymorphic Cross-Module Linkages (`res_model` + `res_id`)
- **Prohibition of Direct Cross-Module Foreign Keys**:
  - Direct PostgreSQL foreign key constraints (e.g. `ForeignKey("accounting_invoices.id")`) across separate modular domains are strictly prohibited.
  - Hard schema foreign keys bind separate module tables physically in the database engine, rendering independent module uninstallation, hot-reloading, or deactivation impossible without database constraint violations or hazardous cascading deletes.
- **Polymorphic Reference Standard**:
  - All cross-module entity relationships MUST use the decoupled polymorphic linkage pattern:
    - `res_model: Mapped[str]`: Target entity model namespace identifier (e.g. `"accounting.invoice"`, `"crm.lead"`, `"inventory.item"`).
    - `res_id: Mapped[uuid.UUID]`: Target entity primary key UUID.
  - Entity lookups and validations are resolved dynamically through Kernel service APIs, event subscribers, or background jobs.

#### 6.3.3 Kernel Topological Dependency Enforcement (التحقق الطوبولوجي من التبعيات)
- **Dependency Inversion Guard**: A module cannot be deactivated if any currently active downstream modules declare it as a dependency in their `manifest.py`.
- **Topological Order**: The Kernel dependency resolver verifies that deactivation follows reverse topological DAG order, preventing orphaned references and dead execution loops.



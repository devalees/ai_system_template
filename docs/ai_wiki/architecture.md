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

---

### 6.4 Automated Model-Level Permission Harvester & Bidirectional Group Governance
- **Zero-Manual-Permission Engine (`backend/modules/base/identity_rbac/harvester.py`)**:
  - Automatically inspects all SQLAlchemy declarative models inheriting from `Base` across all registered modules in the system.
  - Automatically derives canonical permission codes formatted as `{module}.{resource}.{action}` (e.g. `identity_rbac.user.create`, `audit.audit_log.read`, `documents.document_attachment.delete`).
  - Auto-provisions the 4 canonical CRUD capabilities (`create`, `read`, `update`, `delete`) for every business model, ignoring transient association link tables (`*Link`).
  - Collects custom manifest-declared capabilities via `ModuleManifest.custom_permissions`.
  - Idempotently links all harvested permissions to the primary `"Super Administrators"` group.
  - Integrated directly into both `backend/setup_database.py` and `Kernel.bootstrap()`.
- **Bidirectional Group-User Management**:
  - Group payloads accept `user_ids: List[UUID]` during creation (`GroupCreate`) and partial updates (`GroupUpdate`).
  - Read schemas return `users_count: int` on lists and a detailed `users: List[UserSummary]` member list on `GET /groups/{id}` (`GroupDetailRead`).
  - Dedicated granular membership routes:
    - `GET /api/v1/identity_rbac/groups/{group_id}/users`
    - `POST /api/v1/identity_rbac/groups/{group_id}/users/{user_id}`
    - `DELETE /api/v1/identity_rbac/groups/{group_id}/users/{user_id}`

---

### 6.5 Primary Root Admin Immunity & Hierarchical Superuser Governance (`is_primary_admin`)
- **The Root Anchor Entity (`is_primary_admin: bool = True`)**:
  - The initial administrator provisioned during `backend/setup_database.py` is designated as the sole Primary Root Admin (`is_primary_admin = True`, `is_superuser = True`).
  - Solves the flat superuser privilege vulnerability, preventing rogue takeovers, hostile lockouts, and accidental founder account deletion.
- **Hierarchical Governance Rules**:
  - **Undeletability & Immunity**: The Primary Root Admin cannot be soft-deleted by anyone under any circumstances (`403 Forbidden`).
  - **Modification Immunity**: Other users (including secondary superusers) are barred from modifying the Primary Admin's record (`403 Forbidden`).
  - **Self-Protection Guards**: The Primary Admin cannot revoke their own `is_superuser` status or deactivate (`is_active = False`) their own root account (`400 Bad Request`).
  - **Superuser Provisioning Monopoly**: Only the Primary Admin can grant or revoke `is_superuser = True` or provision new superuser accounts. Secondary superusers attempting to create or promote superusers receive `403 Forbidden`.
  - **Superuser Peer Protection**: Secondary superusers cannot modify, demote, or soft-delete other secondary superusers; only the Primary Admin holds administrative lifecycle authority over secondary superusers.

---

### 6.6 Enterprise Authentication Security (Decoupled Credentials, Email Tokens & 2FA / TOTP)
- **Credential Decoupling & Authenticated Password Change**:
  - `password` field completely eliminated from `UserUpdate` schema and generic user profile patching (`PATCH /api/v1/identity_rbac/users/{user_id}`) per OWASP ASVS and NIST SP 800-63B standards.
  - Dedicated endpoint `POST /api/v1/identity_rbac/auth/change-password` requiring active Bearer token, verifying `current_password` against native bcrypt hash, enforcing `new_password` complexity and confirmation match, and blocking redundant password churn.
- **Single-Use Redis Token Engine & Email Verification**:
  - Redis-backed time-limited tokens with atomic `GETDEL` single-use burning to defeat replay and race conditions.
  - **Forgot/Reset Password Flow**: `POST /api/v1/identity_rbac/auth/forgot-password` dispatches 15-minute expiring tokens via `MailService.enqueue_mail` with constant response times defeating email enumeration; `POST /api/v1/identity_rbac/auth/reset-password` consumes the token and updates the hash.
  - **Account Email Verification**: Added `email_verified: bool` on `User`; newly self-registered accounts trigger welcome verification dispatch; completed via `POST /api/v1/identity_rbac/auth/verify-email`.
- **Two-Factor Authentication Subsystem (RFC 6238 TOTP & Recovery Codes)**:
  - Backed by `pyotp` RFC 6238 time-based one-time password algorithm with clock skew window tolerance.
  - `User` schema attributes: `two_factor_enabled: bool`, `two_factor_secret: str`, `two_factor_recovery_codes: List[str]` (JSONB).
  - **Setup (`POST /api/v1/identity_rbac/auth/2fa/setup`)**: Authenticated users receive Base32 secret and `otpauth://` QR URI.
  - **Enablement (`POST /api/v1/identity_rbac/auth/2fa/enable`)**: Confirms TOTP code, generates 8 alphanumeric emergency recovery codes stored as SHA-256 hashes, and enables 2FA.
  - **Two-Step Login Handshake**: If `two_factor_enabled == True`, `POST /api/v1/identity_rbac/auth/login` returns an intermediate 5-minute signed JWT `mfa_token` with `mfa_required: true`.
  - **Challenge Verification (`POST /api/v1/identity_rbac/auth/2fa/verify`)**: Validates `mfa_token` and accepts either a live 6-digit TOTP code or an emergency recovery code (atomically burned from user records upon use).
  - **Disabling (`POST /api/v1/identity_rbac/auth/2fa/disable`)**: Requires re-authenticating current password plus TOTP or recovery code to prevent session hijacking.

---

### 6.7 Universal Modular Settings & Configuration Engine Standard

#### 6.7.1 Architectural Boundary: Tenant Identity vs. Modular Policies
To maintain high architectural integrity and prevent continuous schema churn, the Sovereign platform strictly enforces a clean boundary between tenant identity and operational configurations:
- **Tenant Identity (SQL Table `companies`)**: Strictly reserved for core physical entity attributes: `id`, `name`, `code`, `currency_id`, `email_domain`, `is_active`, `deleted_at`.
- **Operational Policies & Configuration (`ModuleSettings` JSONB + Redis)**: All module-level switches, feature toggles, security rules, numerical thresholds, and business policies (e.g. `allow_registration`, `enforce_2fa`, `default_from_email`, `retention_days`) MUST be managed via the Settings Engine.
- **Rule for All AI Agents**: **NEVER** add ad-hoc boolean flags, policy columns, or feature toggles directly to `Company` or other core domain models. Always declare them as typed Module Settings.

#### 6.7.2 Self-Describing Typed Settings Specification
Every module that supports configurable behavior defines a `settings.py` inside its module directory containing a Pydantic `BaseModel`. Every setting field must include rich metadata:
1. `title`: Human-readable display label for UI checkboxes, dropdowns, and form inputs.
2. `description`: Comprehensive explanation of the setting's business logic, default behavior, and operational impact.
3. `type`: Explicit data type (`boolean`, `integer`, `float`, `string`, `select`, `secret`).
4. `default`: Sensible fallback value when the tenant has not configured custom overrides.
5. `options`: If choice-based (`select`), an explicit list of `[{"value": ..., "label": ...}]` pairs.
6. `category`: Grouping for UI sectioning (e.g. `"User Onboarding"`, `"Security & Authentication"`).

```python
# Example: backend/modules/base/identity_rbac/settings.py
class IdentitySettings(BaseModel):
    allow_registration: bool = Field(
        default=False,
        title="Allow Public Self-Registration",
        description="Allow external users to create accounts without prior administrator invitation.",
        json_schema_extra={"category": "User Onboarding"}
    )
    enforce_2fa: bool = Field(
        default=False,
        title="Enforce Two-Factor Authentication (2FA)",
        description="Require all users within this organization to enable 2FA before accessing system resources.",
        json_schema_extra={"category": "Security & Authentication"}
    )
    password_min_length: int = Field(
        default=8,
        ge=6,
        le=128,
        title="Minimum Password Length",
        description="Minimum number of characters required for user passwords.",
        json_schema_extra={"category": "Security & Authentication"}
    )

SettingsService.register_module_settings("identity_rbac", IdentitySettings)
```

#### 6.7.3 Kernel Discovery & Transparent Fallback Merging
- **Automatic Kernel Discovery**: During `Kernel.load()`, the micro-kernel automatically detects and imports `settings.py` across all loaded modules in topological order.
- **Transparent Fallback Merging**: When `SettingsService.get_settings(db, module_name, company_id)` is invoked:
  $$\text{effective\_settings} = \{\dots\text{defaults}, \dots\text{stored\_tenant\_overrides}\}$$
  If a tenant company has never customized settings, the call seamlessly returns validated defaults without requiring prior database row instantiation.
- **Sub-Millisecond Redis Caching**: Cached under `sovereign:settings:{company_id}:{module_name}` with 1-hour TTL and automated invalidation on `update_settings()`.

#### 6.7.4 Dynamic API Introspection & FastMCP / Hermes Reflection
- `GET /api/v1/settings/{module_name}`: Returns `settings_data` (current effective values) alongside `fields` (the self-describing list of `SettingFieldMeta` containing keys, labels, descriptions, types, defaults, choices, and categories).
- Enables frontend admin dashboards to dynamically render full settings panels with zero hardcoded form templates.
- Enables autonomous Hermes AI agents and FastMCP tools to inspect configurable options, validate parameters, and adjust tenant configurations deterministically.

---

### 6.8 Universal Hierarchical Category & CategorizableMixin Standard

#### 6.8.1 Architectural Purpose & Distinction: Category vs. Tag
To maintain structured, scalable taxonomy across the Sovereign platform without repeating schema boilerplate across modules:
- **`Tag` (`lookup_tags`)**: Flat, non-hierarchical, many-to-many labels (e.g. `VIP`, `Urgent`, `Review-Required`) used for fluid ad-hoc classification.
- **`Category` (`lookup_categories`)**: Formal, multi-tenant, **hierarchical parent/child tree** taxonomy (e.g., *Legal $\rightarrow$ Contracts $\rightarrow$ NDAs* or *IT $\rightarrow$ Hardware $\rightarrow$ Laptops*).

#### 6.8.2 Core Primitives: Model, Tree Traversal & Mixin
1. **The `Category` Model ([`backend/modules/base/lookups/models.py`](file:///home/ehab/Desktop/economy_editor/backend/modules/base/lookups/models.py))**:
   - Multi-tenant (`company_id`, UUID, audit timestamps, soft-delete).
   - Polymorphic scope discriminator (`res_model: str`, e.g., `"document"`, `"mail_template"`, `"product"`, `"partner"`).
   - Self-referential hierarchy: `parent_id: Optional[UUID]` with `parent` and `children` relationships.
   - Rich metadata: `name`, `code` (unique per scope), `description`, `color`, `icon`, `sequence`.
2. **The `CategorizableMixin` ([`backend/core/base_models.py`](file:///home/ehab/Desktop/economy_editor/backend/core/base_models.py))**:
   - Any domain entity in any module (e.g. `DocumentAttachment`, `MailTemplate`, future ERP models) inherits `CategorizableMixin` to gain `category_id: Mapped[Optional[UUID]]` foreign key linkage to `lookup_categories.id`.
3. **Cycle Prevention & Tree API**:
   - `CategoryService` validates that no category can be assigned to itself or any of its descendants as parent, strictly rejecting circular tree loops (`CIRCULAR_CATEGORY_DEPENDENCY` HTTP 400).
   - `GET /api/v1/lookups/categories/tree` provides full recursive nested tree visualization for UI tree navigators and menus.
   - Breadcrumb full paths (e.g., `Corporate Documents / Legal Contracts / Non-Disclosure Agreements`) are dynamically resolved.

---

### 6.9 Master Data Lookups Enterprise CRUD & Postman Sub-Folder Architecture

#### 6.9.1 Complete REST Lifecycle & Typed PATCH Schemas
All master data lookup models in [`backend/modules/base/lookups/models.py`](file:///home/ehab/Desktop/economy_editor/backend/modules/base/lookups/models.py) expose full enterprise CRUD endpoints (`GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`):
- **Countries**: `CountryCreate`, `CountryUpdate`, `CountryRead` (codes auto-uppercased).
- **Cities**: `CityCreate`, `CityUpdate`, `CityRead` (FK verified against tenant's countries).
- **Currencies**: `CurrencyCreate`, `CurrencyUpdate`, `CurrencyRead` (currency code auto-uppercased).
- **Units of Measure (UOM)**: `UnitOfMeasureCreate`, `UnitOfMeasureUpdate`, `UnitOfMeasureRead` (precision rounding).
- **Tax Types**: `TaxTypeCreate`, `TaxTypeUpdate`, `TaxTypeRead` (rates, inclusive/exclusive toggle).
- **Tags**: `TagCreate`, `TagUpdate`, `TagRead` (color, model target).
- **Categories**: Full CRUD, nested tree API, breadcrumb path computation, and cycle prevention.

All `DELETE /{id}` endpoints execute soft-deletion via `SoftDeleteMixin` (`deleted_at = utcnow()`, `deleted_by_id = current_user.id`), automatically excluded from active queries by the global database interceptor.

#### 6.9.2 Hierarchical Postman Sub-Folder Organization
To prevent bloated flat lists in API client collections:
- The Postman Exporter ([`backend/core/exporter.py`](file:///home/ehab/Desktop/economy_editor/backend/core/exporter.py)) dynamically inspects OpenAPI tag arrays. When endpoints share a primary module tag (`tags[0]`) and have distinct sub-tags (`tags[1]`), it organizes them into clean nested subfolders:
  - `Normalized Master Data & Lookups`:
    - 📁 `Categories`
    - 📁 `Units of Measure`
    - 📁 `Countries`
    - 📁 `Cities`
    - 📁 `Currencies`
    - 📁 `Tax Types`
    - 📁 `Tags`
    - ⚡ `Bootstrap Company ISO Lookups`
- All path parameters (`{id}`) dynamically resolve to the specific active entity environment variable (`{{active_country_id}}`, `{{active_city_id}}`, `{{active_currency_id}}`, etc.), capturing newly created IDs via automated Postman test scripts.

---

### 6.10 Event-Driven Automated Actions (TCA) Subsystem & Action Registry Standard

#### 6.10.1 Architectural Philosophy: Zero Hardcoded Side-Effects
In the Sovereign platform, business side-effects (e.g. sending emails on registration, alerting managers on status change, updating related balances) MUST NOT be hardcoded into route handlers. Instead, the platform decouples business workflows into three distinct primitives:
1. **Trigger**: When an event occurs (`on_create`, `on_update`, `on_delete`, `on_state_change`, `on_time_interval`, `manual`).
2. **Condition**: An in-memory evaluation of a declarative universal AST filter tree (`ASTConditionEvaluator`) against the trigger record and previous field values (`old:field`).
3. **Action**: Invocation of a registered, typed action handler (`BaseActionHandler`).

#### 6.10.2 Pluggable Action Handler Registry
All business capabilities register with the central `ActionRegistry` ([`backend/modules/base/automated_actions/engine/registry.py`](file:///home/ehab/Desktop/economy_editor/backend/modules/base/automated_actions/engine/registry.py)):
- `send_email`: Dispatches transactional email via `mail_gateway` with Jinja2 context interpolation.
- `send_notification`: Delivers in-app, WebPush, or push notifications via `notification_engine`.
- `post_chatter`: Appends comments, audit notes, or AI findings into entity chatter threads via `chatter`.
- `update_record`: Directly mutates fields on the trigger record or related relational entities.
- `create_record`: Instantiates new records in any loaded platform module.
- `invoke_webhook`: Dispatches signed HTTP POST/PUT requests to external third-party endpoints with retry.

#### 6.10.3 Dynamic Introspection & FastMCP Reflection
- `GET /api/v1/automated_actions/action-types` exposes all registered action handlers and their generated Pydantic JSON schemas.
- Allows frontend admin interfaces to render action configuration forms dynamically with zero frontend code changes.
- Allows autonomous Hermes AI agents to introspect available business tools and execute automated actions dynamically.

#### 6.10.4 Execution Resilience, Celery Offloading & Recursion Guard
- **Execution Modes**: Synchronous (`SYNC`) for immediate atomic mutations, or Asynchronous (`ASYNC_CELERY`) for I/O operations (emails, webhooks).
- **Infinite Loop Protection**: `TCADispatcher` enforces a configurable cascading recursion depth limit (`max_action_depth`, default 5) via `ContextVar` to halt runaway recursive trigger cascades.
- **Audit Telemetry**: Every execution generates an immutable `ActionExecutionLog` tracking latency, status (`SUCCESS`, `FAILED`, `SKIPPED`), and context diffs.

#### 6.10.5 Model & Field Introspection & Pre-Flight Validation API
To guarantee data integrity and empower dynamic frontend configuration and autonomous AI agents:
- **Model Discovery API (`GET /api/v1/automated_actions/introspection/models`)**:
  - Dynamically inspects all registered SQLAlchemy ORM models inheriting from `Base`.
  - Exposes `name`, `table_name`, `module`, and docstring description.
- **Field Specification API (`GET /api/v1/automated_actions/introspection/models/{model_name}/fields`)**:
  - Reflects all columns, SQL data types, nullability, requirement flags (`required: bool`), primary keys, foreign key targets, and enum choices.
- **Pre-Flight Schema Validation**:
  - Intercepts `POST /api/v1/automated_actions/rules` and `PATCH /api/v1/automated_actions/rules/{id}` before writing to the database.
  - For `create_record`: Validates that `target_model` exists, all non-nullable columns without defaults are present in `field_values`, and field names are valid attributes.
  - For `update_record`: Validates that all keys in `field_values` correspond to valid existing columns on the target model.
  - Raises machine-actionable `422 Unprocessable Entity` errors with explicit field error descriptions before broken rules can be committed.

---

### 6.11 Universal Headless Dynamic Reporting & Document Engine

#### 6.11.1 Philosophy & Headless Boundary
The `reporting` module (`backend/modules/base/reporting/`) provides enterprise-grade, domain-agnostic reporting and document generation strictly adhering to the Sovereign **headless architecture boundary**:
- **Zero Frontend UI in Backend**: No templates, HTML forms, or UI controls are stored or rendered in the backend.
- **Structured Data for UI & AI**: Serves pure aggregated JSON datasets (`POST /api/v1/reporting/{report_code}/data`) containing metadata, columns, row records, and summary aggregates for frontend dashboard widgets or autonomous AI analysis.
- **Headless Binary Generation**: Dynamically compiles and streams downloadable or persistable binary artifacts (PDF, Excel `.xlsx`, CSV) on demand for exports, Celery background worker tasks, and automated action email attachments.

#### 6.11.2 Core Data Models
1. **`ReportDefinition` (`reports_definitions`)**:
   - Stores tenant-scoped dynamic report definitions supporting both Tabular and Document layouts.
   - Declarative JSONB configurations: `selected_fields` (column projections), `filters` (AST filter trees matching Universal Query Engine grammar), `group_by` (grouping columns), `aggregations` (mapping of field to function: `sum`, `count`, `avg`, `min`, `max`), and `order_by`.
   - **Document Reporting Attributes**:
     - `report_type`: `"tabular"` or `"document"` (default `"tabular"`).
     - `document_title`: Formal document display title (e.g. `"Tax Invoice"`, `"Sales Order"`, `"Quotation"`).
     - `header_fields`: Key fields rendered in the document header card (supports dot-notation, e.g. `order_date`, `currency.code`).
     - `recipient_fields`: Customer/partner fields rendered in the recipient card (e.g. `partner.name`, `partner.email`, `partner.city.name`).
     - `lines_relationship`: 1:M relationship attribute name on target model for line items (e.g. `"order_lines"`, `"invoice_lines"`, `"cities"`).
     - `lines_fields`: Fields projected on each line item (supports line-level dot-notation, e.g. `product.name`, `quantity`, `unit_price`, `subtotal`).
   - Optional foreign key link to default `ReportTemplate`.
2. **`ReportTemplate` (`report_templates`)**:
   - Enterprise document styling configuration supporting company branding.
   - Configuration attributes: `page_size` (`A4`, `Letter`), `orientation` (`portrait`, `landscape`), `primary_color` (hex), `secondary_color`, `font_family`, `show_company_logo`, `show_page_numbers`, `header_text`, `footer_text`, and `custom_css_variables` (JSONB).
   - In-memory fallback mechanism: When a tenant hasn't defined a custom template, the system transparently resolves a sensible corporate default (`standard_clean`).

#### 6.11.3 Dynamic Query & Relational Join Engine (`DynamicReportQueryEngine`)
- **Multi-Hop Relational Dot-Notation Resolution**:
  - Automatically resolves dot-separated field paths (`rel.col`, `rel1.rel2.col`, `partner.city.country.name`) across any depth.
  - Dynamically inspects SQLAlchemy ORM `mapper.relationships`, generating unique, isolated aliased entities (`aliased(TargetModel, name="rel_...")`) to eliminate table name collisions (including self-referencing hierarchies like `Category -> parent -> parent`).
  - Caches join paths within each query lifecycle to ensure multiple fields sharing prefixes generate only a single SQL `LEFT OUTER JOIN`.
  - Injects strict multi-tenant isolation (`company_id = active_company`) and soft-delete guards (`deleted_at IS NULL`).
- **Transactional Document Mode (`execute_document_query`)**:
  - Targets a specific business entity instance by `record_id`.
  - Resolves parent record with all M:1 dot-notation header and recipient fields.
  - Dynamically queries 1:M child line items via `lines_relationship`, resolving line fields and computing line-level financial summaries (subtotals, taxes, totals).

#### 6.11.4 Multi-Format Headless Renderers
- **`JSONReportRenderer`**: Pure structured dictionary with metadata, columns, rows, aggregates, and document cards.
- **`CSVReportRenderer`**: High-performance RFC 4180 CSV generation with UTF-8 Byte Order Mark (`\ufeff`) for seamless Arabic and multilingual UTF-8 decoding in Microsoft Excel.
- **`ExcelReportRenderer`**: OpenPyXL-based spreadsheet generation featuring styled company header blocks, colored column headers, zebra striping, accounting-formatted numeric grand totals, and auto-fitted column widths.
- **`PDFReportRenderer`**: ReportLab Platypus executive layout engine:
  - **Document Mode**: Renders formal business documents (Invoices, Sales Orders) with company logo, document reference box, recipient/billing card, lines table grid with word-wrapped descriptions, financial totals summary card (Subtotal, Taxes, Grand Total), and two-pass `NumberedCanvas` delivering dynamic `"Page X of Y"` running footers.
  - **Tabular Mode**: Renders multi-column aggregated data tables with zebra striping and summary rows.

#### 6.11.5 Event-Driven TCA Integration (`GenerateReportActionHandler`)
- Registered in `ActionRegistry` under `action_type = "generate_report"`.
- Configuration schema `GenerateReportActionConfig`: `report_code`, `format` (`pdf`, `xlsx`, `csv`), `parameters`, `template_id`, `attach_to_record` (bool), `send_email` (bool), `recipient_email`.
- Seamlessly bridges document generation with the Event-Driven Automated Actions subsystem, headlessly rendering documents on triggers (e.g. invoice creation, state transitions), attaching files to records via `DocumentService`, and dispatching delivery emails via `MailService`.

#### 6.11.6 Document Attachment Storage Integration
- Report exports can be persisted directly into the platform's Content-Addressable Storage (CAS) via `DocumentService.create_attachment()`.
- Returned metadata includes `attachment_id`, `file_name`, `file_size`, `mime_type`, `res_model`, and `res_id`, enabling immediate access via standard document endpoints.

#### 6.11.7 Multi-Hop Model & Field Introspection API
- **Recursive Depth Inspection (`GET /api/v1/automated_actions/introspection/models/{model_name}/fields?depth=N`)**:
  - Exposes all ORM relationships (`MANYTOONE`, `ONETOMANY`, `MANYTOMANY`) with foreign keys and collection indicators.
  - When `depth > 1`, recursively nests target model fields and relationships up to depth 3, empowering frontend field tree selectors and autonomous AI agents.
- **Relational Path Validation (`resolve_field_path`)**:
  - Validates dot-paths against mappers before query compilation, returning the terminal column type, title, and relationship traversal chain.

### 6.12 Field-Level Access Control (FLAC) & Effective Permissions Engine

#### 6.12.1 Overview & "Role Explosion" Prevention
Traditional enterprise RBAC systems suffer from "Role Explosion" where every slight variation in user permission requirements leads to proliferating synthetic roles (e.g. `Accountant_Without_Salary_View`, `Sales_With_Tax_Edit`).
The Sovereign Platform eliminates Role Explosion through a dual-mechanism security architecture:
1. **Direct User-Level Overrides (`UserPermissionLink`)**:
   - Allows fine-grained, direct permission grants (`is_granted=True`) or explicit revocations (`is_granted=False`) on individual User accounts or autonomous AI Agent identities.
   - Calculates effective permission sets deterministically via:
     $$\text{Effective Permissions} = \left( \bigcup_{g \in \text{Groups}} \text{Permissions}(g) \right) \cup \text{Direct Grants} \setminus \text{Direct Revocations}$$
2. **Field-Level Access Control (FLAC)**:
   - Extends the authorization boundary beneath the coarse record/model level down to individual model attributes.
   - Uses the canonical permission syntax: `{module}.{resource}.{field_name}:{read|write}` (e.g., `identity_rbac.company.tax_id:read`).

#### 6.12.2 Model Architecture & Guard Declarations
1. **`Permission` (`permissions`)**:
   - `permission_type`: String enum (`"model"` | `"field"`).
   - `field_name`: Optional string storing the target attribute name for field permissions.
2. **`Group` (`groups`)**:
   - `group_type`: String enum (`"role"` | `"department"` | `"custom"`), clarifying functional job roles from organizational departments.
3. **`UserPermissionLink` (`user_permission_links`)**:
   - Junction table linking `user_id` and `permission_id` with `is_granted: bool`.
   - Supports additive micro-privileges and negative explicit carve-outs.
4. **Declarative Guard Reflection (`__guarded_fields__`)**:
   - Models declare sensitive attributes declaratively on their classes:
     ```python
     class Company(BaseModel):
         ...
         __guarded_fields__ = {
             "tax_id": {"read_permission": "identity_rbac.company.tax_id:read", "write_permission": "identity_rbac.company.tax_id:write"},
             "settings": {"read_permission": "identity_rbac.company.settings:read", "write_permission": "identity_rbac.company.settings:write"},
         }
     ```
   - Central registry `_GUARDED_FIELDS_MAP` automatically catalogues guarded attributes across all loaded models upon startup.

#### 6.12.3 Egress Filtering & Ingress Mutation Validation (`FLACService`)
- **Egress Read Sanitization (`sanitize_read_fields`)**:
  - Automatically filters model instances, Pydantic schemas, or dictionaries before HTTP serialization.
  - If the caller (human user or AI agent) lacks `{module}.{resource}.{field}:read`, the guarded attribute is completely pruned from dictionaries or set to `None` on object instances.
  - Supports recursive sanitization across lists and nested child records.
- **Ingress Write Validation (`validate_write_fields`)**:
  - Intercepts incoming mutation payloads (`POST`, `PUT`, `PATCH`) before database execution.
  - If any payload field is guarded and the caller lacks `{module}.{resource}.{field}:write`, the operation is aborted with HTTP 403 Forbidden: `"Forbidden: write access denied on field '{field}'"`.
- **First-Class AI Agent Governance & Superuser Bypass**:
  - AI agents (`user_type="agent"`) are evaluated symmetrically against the exact same FLAC policies as human users, preventing autonomous agents from inadvertently leaking or modifying sensitive financial/PII attributes.
  - Platform Super Administrators (`is_superuser=True`) automatically bypass all model and field checks.

#### 6.12.4 Automated Permission Harvester
- `PermissionHarvester.harvest_all()` automatically discovers all `__guarded_fields__` declared across registered models.
- Generates corresponding read and write `Permission` records (`permission_type="field"`).
- Idempotently links all harvested field permissions to the primary "Super Administrators" group.

#### 6.12.5 Effective Permissions & Overrides REST API
- `GET /api/v1/identity_rbac/auth/me/permissions`: Returns caller's full effective permission matrix (model permissions, field permissions, and groups).
- `GET /api/v1/identity_rbac/users/{user_id}/permissions`: Administrator introspection of target user's effective permissions and explicit direct overrides.
- `POST /api/v1/identity_rbac/users/{user_id}/permissions`: Sets or updates a direct grant or explicit negative revocation override (`is_granted: bool`).
- `DELETE /api/v1/identity_rbac/users/{user_id}/permissions/{permission_id}`: Removes a direct override, reverting the user to standard group-inherited permissions.




# Architectural Specification & Plan: Sovereign Headless Backend Platform

- **Status**: IN_PROGRESS <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `main`
- **Last Updated**: 2026-09-13 23:48:00+03:00
- **Document Path**: `docs/plans/backend_architecture_plan.md`

---

## 1. Objective & Scope

Design and build a **Metadata-Driven, Headless Modular Micro-Kernel Backend Platform** that serves as the core data, business logic, and API engine for sovereign enterprise applications. 

The backend is 100% decoupled from presentation views (pure headless data APIs) and natively integrates with the Sovereign AI Agent ecosystem (`agent_service/`).

---

## 2. Dimension 1: Architecture & Philosophy (Agreed & Synthesized)

The architectural philosophy is anchored by 8 core principles:

### Principle 1: Modular Micro-Kernel Core (Headless & Extensible)
* **Micro-Kernel Paradigm**: A lean, robust foundational Kernel providing baseline lifecycle management, dynamic module registration, and inter-module communication (inspired by Linux kernel modularity and extensible ERP engines like Odoo/Frappe).
* **Pluggable Domain Modules**: Domain applications (Sales, CRM, Accounting, Invoicing, Inventory, custom verticals) are packaged as modular, decoupled packages that can be installed, enabled, disabled, or uninstalled dynamically without modifying Kernel source code.
* **Pure Data & API (Headless)**: 100% decoupled from UI/views; strictly exposes structured REST / JSON-RPC / WebSocket data endpoints.
* **Acyclic Dependency Enforcement**: The Kernel discovers module manifests and strictly validates an acyclic dependency graph (DAG) during bootstrap.

### Principle 2: Per-Module AI/Agent-Enablement Toggle
* **Granular Capability Flag**: Each module manifest declares `ai_enabled: bool`.
* **Dynamic FastMCP Registration**: When an AI-enabled module is loaded, the Kernel automatically scaffolds and exports its domain tools, schemas, and memory categories to the Hermes AI Agent via FastMCP.
* **Hybrid Workloads**: High-security, sensitive, or routine modules can remain strictly deterministic and non-AI, eliminating LLM prompt bloat and avoiding hallucination risks.

### Principle 3: Event-Driven Automated Actions Engine (Trigger-Condition-Action)
* **Actions as First-Class Primitives**:
  * **Systematic Actions**: Core internal state transitions and invariants.
  * **Automated Actions**: Dynamic, administrator- or user-configured business rules running automatically on triggers.
  * **Manual Actions**: User-invoked batch or single-record actions.
* **Declarative Trigger-Condition-Action (TCA) Pipeline**:
  * *Triggers*: ORM lifecycle hooks (`on_create`, `on_update`, `on_delete`, `on_state_change`), scheduled/cron intervals, or external webhooks.
  * *Conditions*: Evaluated in-process via a sandboxed expression evaluator against record attributes and relational fields.
  * *Actions*: Mutations in same/other modules (`create`, `update`), external dispatches (email, webhooks), or dispatching autonomous tasks to AI agents.
* **Zero Hardcoding**: Eliminates hardcoded business side-effects; provides an immutable execution audit log (`action_execution_log`).

### Principle 4: Universal Advanced Filtering & Query Engine
* **Universal Kernel Specification**: A centralized query engine implemented at the Kernel level so that every existing and future module automatically inherits advanced search and filtering without writing custom query endpoints.
* **Nested Boolean Trees**: Supports arbitrary compound condition trees (`AND`, `OR`, `NOT` logical groups).
* **Rich Domain Operators**: Equality (`eq`, `neq`), substrings (`contains`, `starts_with`, `ends_with`), set inclusion (`in`, `not_in`), numeric/date ranges (`between`, `gt`, `gte`, `lt`, `lte`), nullability checks (`is_null`), and cross-relational path traversals (e.g. `order.customer.tier == 'VIP'`).
* **Deterministic AST Compilation**: Compiles declarative JSON payloads directly into parameterized database queries, safeguarding against SQL injection and guaranteeing query planner index usage.

### Principle 5: Layered Core Infrastructure (Base Utilities vs. Optional Apps)
* **Built-in Base Utility Modules (Installed by Default)**:
  * *File & Document Storage*: Blob storage, metadata indexing, MIME handling, versioning, and document parsing.
  * *Scheduler & Calendar Engine*: Cron scheduling, event timelines, deadlines, and recurring job queues.
  * *Communication & Notification Hub*: Inbound/outbound email gateway, push alerts, and webhook dispatcher.
  * *Audit & Activity Logging*: Immutable historical trail of entity mutations.
  * *Identity & Access Management*: Authentication, tenant context, and session management.
* **Seamless Utility Inheritance**: Any new domain module automatically leverages these base utilities (e.g., attaching receipts to invoices, scheduling calendar alerts on opportunities).

### Principle 6: Authentication & Role-Based Access Control (RBAC)
* **Pragmatic Model-Level Access Control**: Access control is enforced primarily at the Model / Table level (`create`, `read`, `update`, `delete`).
* **Hierarchical Role/Group Inheritance**: Users belong to Groups/Roles (e.g. *Accountant*, *Sales Manager*) and inherit combined permissions.
* **User-Level Overrides / Exceptions**: Specific model permissions can be granted directly to an individual user as an exception/addition without altering group definitions.

### Principle 7: Native Multi-Tenancy & Multi-Company Isolation
* **Multi-Company Core**: Multiple operating legal entities and companies within a single deployment.
* **Strict Boundary Enforcement**: Zero cross-tenant data leakage.
* **Kernel-Enforced Tenant Scoping**: Queries and actions automatically inject `WHERE company_id = :active_company_id` at the ORM/data layer to guarantee tenant isolation across all modules.

### Principle 8: Contextual Communication & Collaboration Subsystem ("Chatter")
* **Universal Record-Level Threading**: Threaded discussions and message logs attached directly to any business document/record via a polymorphic link `(res_model, res_id)`.
* **Dual-Channel Message Types**:
  * *Internal Notes*: Private team comments, handoffs, and mentions (`@user`, `@agent`).
  * *External Messages*: Customer-facing email threads tracked directly on the record.
* **Native AI Agent Participation**: AI agents (Hermes) can inspect thread histories, formulate contextual drafts, and participate as collaborators on any record.

### Principle 9: Per-Module / Per-App Configuration & Settings Engine
* **Dedicated Module Settings**: Every domain application and base utility declares its own structured settings schema (e.g. default currency, rounding rules, email templates, auto-assignment thresholds, prefix sequences).
* **Multi-Tenant Scoping**: Settings can be overridden on a per-tenant/company basis or inherit global platform defaults.
* **Declarative Schema Contracts**: Settings are validated via Pydantic models and exposed through standardized API endpoints (`GET /api/v1/{module}/settings`, `PATCH /api/v1/{module}/settings`), allowing headless clients to render configuration forms dynamically.

### Principle 10: Relational Dynamism & Seed Fixtures (Dynamic Lookups over Static Enums)
* **Dynamic Relational Lookups**: Multi-option choices (e.g., countries, cities, stages, categories, payment terms, units of measure) are modeled as distinct, dynamic database entities rather than static hardcoded code enums.
* **Seed Data & Fixtures on Bootstrap**: System ships with default data fixtures (e.g., ISO countries, standard currencies, default tax types) that are seeded automatically upon initial installation.
* **Tenant Extensibility**: Tenants can add, modify, reorder, or deactivate lookup choices at runtime via standard API endpoints without code deployments or database migrations.
* **Pragmatic Boundary**: Strictly applies relational normalization to domain lookup dimensions while avoiding brittle anti-patterns (such as universal EAV across core entity columns).

### Principle 11: Native Multi-Language (i18n / l10n) Architecture
* **API-Level Internationalization**: Every API endpoint respects the `Accept-Language` HTTP header (or authenticated user language preference, e.g., `en`, `ar`).
* **Translatable Static Content**: System error messages, validation errors, and notification templates are stored in structured translation catalogs (JSON/gettext).
* **Translatable Dynamic Data**: Support for multi-lingual model fields (e.g. product names, category descriptions) stored in structured `JSONB` translation maps (`{"en": "Sales Invoice", "ar": "فاتورة مبيعات"}`) returning the active locale automatically.

### Principle 12: Comprehensive Enterprise Audit Trail & Historical Logging
* **Immutable Mutation Log**: Comprehensive tracking of all database mutations across every module (`AuditLog` table).
* **Audit Metadata Captured**:
  * *Actor*: `user_id` (human user or AI agent).
  * *Context*: `company_id`, client IP address, and user agent.
  * *Operation*: `CREATE`, `UPDATE`, `DELETE`, `STATE_TRANSITION`, or `ACTION_TRIGGER`.
  * *Payload Diff*: Precise JSON diff capturing previous values vs. new values (`before_state`, `after_state`).
* **Auditable Reporting Endpoints**: Standardized API endpoints (`GET /api/v1/audit/logs`, `GET /api/v1/audit/reports`) allowing administrators and auditors to inspect historical record evolution.

### Principle 13: First-Class AI Agent Identity in User & RBAC Model
* **Unified User Model**: The `User` entity explicitly defines `user_type: "human" | "ai_agent"`.
* **Symmetric Authorization**: An AI Agent is registered in the database just like a human employee, assigned its own unique `user_id`, profile metadata, and linked to standard RBAC Groups/Roles (e.g. assigning the `procurement_agent` to the *Procurement Reviewers* group).
* **Token & Identity Verification**:
  * When Hermes interacts via FastMCP or REST API, it authenticates with its designated `agent_user_id` and service token.
  * Standard RBAC permission checks execute identically for humans and agents.
* **Auditing Accountability**: In all audit logs and chatter threads, mutations performed by an agent are unambiguously credited to that specific AI agent identity (`user_type="ai_agent"`).

---

## 3. Technology Stack & Runtime (Dimension 2 — AGREED)

- [x] **Web & API Framework**: **FastAPI** + **Uvicorn** (AGREED)
  * High-throughput asynchronous ASGI runtime.
  * Direct Pydantic v2 schema sharing with `agent_service/`.
  * Native WebSocket/SSE support for chatter, real-time alerts, and agent thought streams.
  * Auto-generated OpenAPI/Swagger documentation (`/docs`).
- [x] **Primary Relational Database**: **PostgreSQL 16** (AGREED)
  * Battle-tested ACID compliance for financial/enterprise transactions.
  * Rich `JSONB` indexing support for flexible metadata and dynamic module attributes.
  * Managed cleanly via Docker and `docker-compose.yml`.
- [x] **Database ORM & Migrations**: **SQLAlchemy 2.0 Async** + **Alembic** (AGREED)
  * Modern async session management (`asyncpg` driver).
  * Ideal for compiling the Universal Filtering AST into parameterized SQL.
  * Programmatic migration runner supporting decoupled modular migrations.
- [x] **Asynchronous Task Queue & Broker**: **Redis** + **Celery** (AGREED)
  * Distributed, reliable task queue for offloading Trigger-Condition-Action events, email dispatches, and heavy background jobs.
  * Redis doubles as high-speed in-memory cache and pub/sub message broker.
- [x] **Data Validation & Contracts**: **Pydantic v2** (AGREED)
  * Universal schema contracts, Rust-speed serialization/validation.
- [x] **Testing & Verification**: **Pytest** + **HTTPX (AsyncClient)** (AGREED)
  * Fast, isolated in-memory testing for every module, action, and API endpoint.

---

## 4. Database & Multi-Tenant Storage Strategy (Dimension 3 — AGREED)

- [x] **Multi-Tenancy Isolation Model**: **Pattern A (Shared Database with Discriminator `company_id`)** (AGREED)
  * Single, high-performance PostgreSQL 16 database.
  * Every entity table includes a `company_id` foreign key.
  * The Kernel automatically injects `WHERE company_id = :active_company_id` into all SQLAlchemy queries and creates via session-level hooks, eliminating accidental cross-tenant data leaks.
  * Delivers maximum connection pool efficiency, simple single-step migrations across the platform, and effortless cross-company consolidation reporting.
- [x] **Dynamic Custom Attributes**: **PostgreSQL `JSONB` (`custom_fields`) + GIN Indexing** (AGREED)
  * Every extensible entity includes a binary JSON column (`custom_fields JSONB DEFAULT '{}'::jsonb`).
  * Backed by PostgreSQL **GIN indexing** (`USING gin(custom_fields)`), enabling sub-millisecond query execution inside nested JSON attributes.
  * Validated dynamically against per-module Pydantic schemas.
  * Allows tenants and modules to define custom attributes on the fly without DDL table locks or database migrations.

---

---

## 5. Asynchronous Execution, Task Queue & Event Bus (Dimension 4 — AGREED)

- [x] **Decoupled Event Pipeline**: **ORM Hooks $\rightarrow$ Redis Broker $\rightarrow$ Celery Worker** (AGREED)
  * Fast API endpoints return immediately in `<20ms`; slow side-effects (sending emails, invoking webhooks, generating PDF documents, running automated business actions) are queued in Celery.
  * In-process event bus catches entity mutations (`before_save`, `after_save`, `on_state_transition`) and dispatches async tasks reliably.
- [x] **Periodic & Cron Automation**: **Celery Beat** (AGREED)
  * Acts as the platform-wide central timer evaluating scheduled automated actions (e.g. daily invoice reminders, periodic reconciliation, status expirations).
- [x] **Real-Time Client Updates**: **Redis Pub/Sub $\rightarrow$ FastAPI WebSockets** (AGREED)
  * Live broadcasting of record chatter updates, user mentions, in-app notifications, and streaming AI agent thought processes to connected frontend/API clients.
- [x] **Resilience & Auditability**: **Action Execution Log** (AGREED)
  * Automatic retry with exponential backoff on transient network failures (e.g. SMTP/Webhook timeouts).
  * Persistent execution status, execution latency, and error tracebacks logged into `action_execution_log`.

---

## 6. Hermes Agent Bridge & MCP Integration (Dimension 5 — AGREED)

- [x] **Automated Action as the AI Execution Bridge** (AGREED)
  * Seamlessly unifies AI automation with the **Trigger-Condition-Action (TCA)** engine (Principle 3).
  * System administrators can attach an Automated Action to *any* module (Sales, Invoicing, Procurement, CRM, etc.) with custom conditions and select the action type: **`invoke_ai_agent`**.
- [x] **Configurable Dynamic Prompt Templates** (AGREED)
  * Administrators define the prompt template with dynamic record interpolations (e.g., `"Analyze vendor invoice #{record.number} for company {record.company.name} and verify line items against PO #{record.po_number}."`).
  * Dispatches an asynchronous Celery task to the Hermes Agent Gateway (`POST http://hermes-template-agent:8643/v1/chat/completions`) with calibrated profile parameters (`orchestrator`, `qa_auditor`, or dynamic specialist).
- [x] **Strict RBAC & Permission Gating** (AGREED)
  * The executing agent profile is treated as a first-class system identity.
  * Hermes can only execute mutations or queries if its scoped token in [`credential_vault.py`](file:///home/ehab/Desktop/economy_editor/agent_service/mcp/credential_vault.py) holds the required model-level permissions for that specific `company_id`.
- [x] **Contextual Feedback Loop** (AGREED)
  * Hermes posts its structured findings, audit verdicts, or synthesized drafts directly into the target record's **Chatter Thread** (Principle 8).
  * The entire interaction is captured in both the backend `action_execution_log` and the Langfuse tracing dashboard (`:3100`).

---

## 7. Comprehensive Architectural Blueprint Status

All 5 core dimensions have been collaboratively brainstormed and agreed upon:
* [x] **Dimension 1**: Architecture & Philosophy (13 core principles including per-app settings, relational dynamism, i18n, audit logging, and first-class AI agent user identity).
* [x] **Dimension 2**: Technology Stack (FastAPI, PostgreSQL 16, SQLAlchemy 2.0 Async, Alembic, Redis + Celery, Pydantic v2).
* [x] **Dimension 3**: Database & Multi-Tenant Storage Strategy (Pattern A: Shared DB with `company_id` + `JSONB` custom fields with GIN indexes).
* [x] **Dimension 4**: Asynchronous Execution & Event Bus (ORM hooks $\rightarrow$ Redis/Celery $\rightarrow$ WebSockets + Celery Beat).
* [x] **Dimension 5**: Hermes Agent Bridge & MCP Integration (Configurable Automated Actions with dynamic prompt templates & RBAC gating).

---

## 8. Implementation Roadmap & Milestones

### Milestone 1: Container Infrastructure & Docker Scaffolding
- [ ] Configure `backend`, `postgres:16-alpine`, `redis:7-alpine`, and `celery_worker` services in Docker Compose.
- [ ] Scaffolding Python dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `celery`, `redis`, `pydantic`.
- [ ] Verify health checks and database connectivity inside the isolated Docker network.

### Milestone 2: Micro-Kernel Core & Dynamic Module Loader
- [ ] Implement `backend/core/kernel.py`: dynamic module discovery, manifest validation (`manifest.py`), and acyclic dependency DAG enforcement.
- [ ] Implement Kernel lifecycle management stages: `discover` $\rightarrow$ `load` $\rightarrow$ `migrate` $\rightarrow$ `bootstrap`.

### Milestone 3: Multi-Tenancy & Database ORM Engine
- [ ] Base SQLAlchemy async declarative model with automatic `company_id` multi-tenancy injection.
- [ ] Extensible `custom_fields JSONB` column with PostgreSQL GIN indexing on base entities.
- [ ] FastAPI session middleware enforcing active `company_id` context on all requests.

### Milestone 4: Universal Advanced Filtering & Query Engine
- [ ] Declarative AST parser and compiler for nested boolean query trees (`AND`, `OR`, `NOT`).
- [ ] Parameterized SQLAlchemy query translation with full operator support (`eq`, `contains`, `in`, `between`, relational traversals).

### Milestone 5: Core Base Utilities (Installed by Default)
- [ ] **Identity & Symmetric RBAC**: `User` model with `user_type: "human" | "ai_agent"`, Groups, model-level CRUD permissions, and user-level overrides.
- [ ] **Multi-Language (i18n / l10n)**: Request language negotiation (`Accept-Language`), translation catalogs, and `JSONB` multi-lingual field support.
- [ ] **Enterprise Audit Trail**: Immutable `AuditLog` table capturing actor, timestamp, operation, and before/after JSON diffs.
- [ ] **Per-Module Settings Subsystem**: Scoped module configuration contracts and API endpoints (`GET/PATCH /api/v1/{module}/settings`).
- [ ] **Dynamic Lookups & Seed Fixtures**: Normalized lookup models (countries, currencies, categories) with auto-seeded default data.
- [ ] **Contextual Chatter & WebSockets**: Polymorphic threaded discussions `(res_model, res_id)` with internal notes, emails, and Redis Pub/Sub WebSocket broadcasting.
- [ ] **File & Document Storage**: Attachment manager supporting blob persistence, MIME metadata, and parsing.

### Milestone 6: Event-Driven Automated Actions Engine (TCA)
- [ ] Trigger registry: ORM lifecycle hooks (`on_create`, `on_update`, `on_delete`, `on_state_change`), Celery Beat cron intervals.
- [ ] Universal condition evaluator running against record attributes and relational paths.
- [ ] Action execution dispatcher: `update_record`, `create_record`, `send_email`, `invoke_webhook`.

### Milestone 7: Hermes Agent Bridge & Dynamic MCP Tool Exposer
- [ ] `invoke_ai_agent` automated action executor calling Hermes Gateway (`:8643`) with dynamic prompt templates.
- [ ] Dynamic FastMCP tool generator reflecting Pydantic schemas from `ai_enabled` modules.
- [ ] Feedback integration posting agent audit findings directly into record Chatter threads.

### Milestone 8: Golden Benchmark Evaluation Suite & Verification
- [ ] Deterministic `pytest` test suite with `httpx.AsyncClient` validating:
  * Multi-tenancy boundary isolation.
  * Universal filtering AST compilation.
  * Symmetric human vs. AI agent RBAC enforcement.
  * Automated action execution and audit trail logging.
  * End-to-end Hermes Agent dispatch and chatter callbacks.

---

## 9. Current Focus
Milestones prioritized and documented. Ready for execution of **Milestone 1: Container Infrastructure & Docker Scaffolding**.

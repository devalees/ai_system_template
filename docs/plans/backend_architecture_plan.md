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

## 4. Pending Dimensions for Collaborative Brainstorming

- [ ] **Dimension 3: Database & Multi-Tenant Storage Strategy** *(Currently in focus)*
  - Multi-tenancy implementation pattern: **Shared Database with Discriminator (`tenant_id`/`company_id`)** vs. **PostgreSQL Schema-per-Tenant** (`tenant_a.*`, `tenant_b.*`).
  - Handling dynamic custom attributes & fields per tenant (PostgreSQL `JSONB` vs. dedicated tables).
- [ ] **Dimension 4: Asynchronous Execution, Task Queue & Event Bus**
  - Event dispatch flow: ORM hooks $\rightarrow$ Redis/Celery queue $\rightarrow$ Action execution $\rightarrow$ WebSocket pub/sub.
  - Periodic / Scheduled cron runner (Celery Beat).
- [ ] **Dimension 5: Hermes Agent Bridge & MCP Integration**
  - Dynamic tool generation from module schemas.
  - Bi-directional communication between backend API and `agent_service` container.

---

## 5. Current Focus
Brainstorm **Dimension 3: Database & Multi-Tenant Storage Strategy** (specifically evaluating Shared DB with `company_id` discriminator vs. Schema-per-tenant).

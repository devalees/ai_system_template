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

---

## 3. Pending Dimensions for Collaborative Brainstorming

- [ ] **Dimension 2: Technology Stack & Language Runtime** *(Currently in focus)*
  - Programming Language (Python, Go, Node/TypeScript, Rust)
  - Web & API Framework (FastAPI, Gin/Go, NestJS, etc.)
  - ORM / Query Layer (SQLAlchemy 2.0 async, Prisma, Ent, etc.)
- [ ] **Dimension 3: Database & Multi-Tenant Storage Strategy**
  - Database Engine (PostgreSQL, SQLite for local/embedded, etc.)
  - Multi-tenancy implementation pattern (Shared DB + discriminator column vs. schema-per-tenant)
- [ ] **Dimension 4: Asynchronous Execution, Task Queue & Event Bus**
  - Task runner / background queue (Redis + Celery / ARQ / TaskIQ, or in-process async)
  - WebSocket / SSE streaming for real-time agent responses and notifications
- [ ] **Dimension 5: Hermes Agent Bridge & MCP Integration**
  - Dynamic tool generation from module schemas
  - Bi-directional communication between backend API and `agent_service` container

---

## 4. Current Focus
Review and refine Dimension 1 with the user, then proceed to brainstorm **Dimension 2: Technology Stack**.

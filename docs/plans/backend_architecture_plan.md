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

### Principle 6: Authentication & Contextual RBAC (Model, Ownership & Inherited Scopes)
* **Hierarchical Role/Group Model**: Users belong to Groups/Roles (e.g. *Accountant*, *Sales Rep*, *Auditor*) with user-level exception overrides.
* **Granular Model-Level Capabilities**: Permissions are explicit per module and model (e.g., `create:crm.lead`, `export:sales.order`, `import:accounting.invoice`). Cross-cutting services (like Import/Export) check target-model capability rather than granting dangerous global access.
* **Three-Tier Record Ownership Scoping**:
  * `GLOBAL`: Can view/mutate all records within the active `company_id`.
  * `TEAM / DEPARTMENT`: Can view/mutate records assigned to their specific team/department.
  * `OWN`: Restricted strictly to records where `created_by_id == user.id` or `assigned_to_id == user.id`.
* **Inherited Permission for Contextual Attachments/Documents**:
  * Attachments and documents attached polymorphically to a business document `(res_model, res_id)` **automatically inherit the parent record's permission**.
  * If a user has read access to `Project #10`, they automatically have read access to attachments on `Project #10`.
  * Standalone documents (not attached to a parent record) enforce standard `OWN` access or explicit user/group sharing.

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

### Principle 14: Universal Advanced Aggregator & Equation Engine (Analytics & KPI Metrics)
* **Kernel-Level Analytics Uniformity**: Symmetrical to the Universal Filtering Engine (Principle 4), a centralized Aggregation & Computation Engine provided by the Kernel so that every existing and future module automatically inherits advanced analytical summaries without writing custom SQL endpoints.
* **Standard & Statistical Aggregations**:
  * Out-of-the-box operations: `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, `COUNT_DISTINCT`, and percentiles.
  * Multi-dimensional grouping: Grouping across multiple attributes (e.g., group by `customer.country`, then by `status`) and temporal buckets (`day`, `week`, `month`, `quarter`, `year`).
* **Complex Computed Expressions & Equations**:
  * Evaluates mathematical equations across aggregated metrics (e.g., `(SUM(revenue) - SUM(cogs)) / NULLIF(SUM(revenue), 0) * 100` for Gross Margin %, or `COUNT(tickets) / NULLIF(COUNT(agents), 0)` for Workload Ratio).
  * Conditional aggregations (e.g., `SUM(amount) FILTER (WHERE status = 'paid')` vs. `SUM(amount) FILTER (WHERE status = 'overdue')`).
* **PostgreSQL Engine Compilation**: Compiles declarative JSON aggregation specifications directly into parameterized SQL with native PostgreSQL aggregate functions, `GROUP BY`, `HAVING`, and window functions, guaranteeing sub-second execution across large datasets.

### Principle 15: Universal Data Import & Export Engine (Batch, Schema-Mapped & Async)
* **Cross-Module Availability**: A centralized import/export subsystem provided by the Kernel, enabling users and external systems to bulk import and export data across any module (e.g., CSV, Excel, JSON).
* **Dynamic Column-to-Schema Mapping**: Users can map arbitrary external file headers to internal model fields, validated dynamically via Pydantic schemas before insertion.
* **Non-Blocking Asynchronous Processing**: Large datasets are processed in the background via Celery workers with chunked batch inserts, avoiding HTTP request timeouts and providing live progress percentages over WebSockets.
* **Granular RBAC Protection**: Strict capability checks (`import:<model>` and `export:<model>`) ensure users can only import/export data for models they are explicitly authorized to manage.

### Principle 16: Unified Atomic Backup & Disaster Recovery (Database + Filestore Bundle)
* **Solving the Database-Filestore Disconnect**:
  * A backup is **never** just an isolated SQL dump. It is a single, self-contained compressed archive bundle (`backup_YYYYMMDD_HHMMSS.tar.gz`) containing:
    1. `dump.sql`: Complete PostgreSQL transactional database dump (`pg_dump`).
    2. `filestore/`: The entire directory of physical document attachments, media, and blobs.
    3. `manifest.json`: System version, migration revision (Alembic hash), company tenant list, file counts, and cryptographic SHA-256 checksums.
* **Relative Content-Addressable Storage (CAS)**:
  * The database never stores brittle absolute host paths. File records store relative storage keys: `filestore/{company_id}/{sha256_hash}`.
  * Restoring the archive bundle onto *any* host machine, folder, or container restores both database records and physical files in 100% synchronized fidelity with zero broken attachment links.
* **Security & Isolation from Public HTTP**:
  * Dangerous raw backup/restore DDL operations are strictly excluded from public HTTP endpoints to prevent remote denial-of-service or database wipe attacks.
  * Driven by standalone, secure CLI scripts (`backup.sh`, `restore.sh` / `backend/scripts/backup.py`).
* **Automated Action & Cron Integration**:
  * Administrators can schedule recurring automated backup snapshots (Daily, Weekly, Monthly) via the **Automated Actions Engine** and Celery Beat, with snapshot records and status logged into `action_execution_log`.
  * Disaster recovery (`restore.sh`) is intentionally restricted to an offline administrator CLI command with confirmation safeguards.

### Principle 17: Dedicated Multi-Channel Push & Notification Engine
* **Dedicated Base Utility Module (`notification_engine`)**: Decoupled from raw WebSocket pipes, providing an intelligent notification hub managing delivery channels, templates, and user preferences.
* **Multi-Channel Delivery Channels**:
  * *Channel 1: In-App WebSockets*: Real-time alerts, bell counter badges, and live chatter updates pushed to active browser/mobile sessions via Redis Pub/Sub.
  * *Channel 2: Web Push Notifications (W3C / VAPID)*: Push notifications delivered to desktop or mobile browsers even when the application tab is closed.
  * *Channel 3: Mobile Push (FCM / APNs)*: Device token registry dispatching native push alerts to iOS and Android clients.
  * *Channel 4: Webhooks*: External systems subscribing to specific notification topics.
* **Per-User Delivery Preferences**: Users configure delivery preferences per category (e.g. *"Purchase Orders: In-App + WebPush; Critical System Alerts: Email + Push; Routine Chatter: In-App only"*).

### Principle 18: Soft Delete, Relational Integrity & Partial Unique Indexes
* **Why Soft Delete is Critical for Business Systems**:
  * *Regulatory & Financial Integrity*: Financial transactions, invoices, ledger entries, and audit logs must never be physically erased.
  * *Accidental Deletion Recovery*: Deletions can be restored in a single click (`deleted_at = None`).
  * *Foreign Key Preservation*: Soft-deleting a Customer preserves all historical Sales Orders and Invoices referencing that `customer_id` without breaking constraints or triggering destructive cascading deletes.
* **Kernel-Enforced Automatic Query Filtering**:
  * Entities include `SoftDeleteMixin` (`deleted_at: Optional[datetime] = None`, `deleted_by_id: Optional[UUID] = None`).
  * In SQLAlchemy 2.0, the Kernel configures `with_loader_criteria` so that `WHERE deleted_at IS NULL` is automatically injected into **100% of SELECT queries across all modules**. Developers never have to remember to write it.
  * Explicit audit override: `select(Model).execution_options(include_deleted=True)` allows recovery screens to query deleted rows.
* **PostgreSQL Partial Unique Indexes**:
  * Solves the unique constraint conflict (e.g., unique customer code or email):
    `CREATE UNIQUE INDEX uq_customer_code ON customers (company_id, customer_code) WHERE deleted_at IS NULL;`
  * Permits re-using a code if an old record was soft-deleted, while strictly guaranteeing uniqueness among active records.
* **Three-Tier Entity Lifecycle Taxonomy**:
  * *Soft-Deletable*: Master Data (Customers, Products, Vendors, Users) and Operational Records (Orders, Invoices, Tasks).
  * *Immutable (Append-Only; Never Deleted)*: General Ledger entries, Audit Logs (`AuditLog`), and Action Execution Logs.
  * *Hard-Deleted*: Transient/ephemeral records (auth cache, temp upload chunks, expired sessions).

---

## 3. Structural Taxonomy: Kernel vs. Base Utilities vs. Pluggable Apps

To maintain strict modularity, clean boundaries, and zero circular dependencies, the backend is organized into three distinct tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     TIER 3: PLUGGABLE BUSINESS APPS (modules/apps/)                    │
│   (Sales, CRM, Accounting, Invoicing, Procurement, Custom Business Verticals...)       │
│   - Declares manifest.py (dependencies, models, schemas, settings, ai_enabled: bool)   │
│   - Inherits base models, lookups, chatter, and attachments without tight coupling     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Extends & Consumes
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                      TIER 2: CORE BASE UTILITIES (modules/base/)                       │
│   (Foundational system services installed out-of-the-box)                              │
│                                                                                        │
│   1. identity_rbac     : Users (human/agent), Groups, 3-tier ownership, JWT & Tokens   │
│   2. settings          : Per-module dynamic settings schemas & tenant overrides        │
│   3. lookups           : Normalized dynamic lookup models (countries, currencies, etc.)│
│   4. audit             : Immutable record mutation logs & audit reporting              │
│   5. chatter           : Polymorphic threaded discussions, email sync & team notes     │
│   6. documents         : Blob attachment manager with parent-inherited permissions     │
│   7. automated_actions : Declarative Trigger-Condition-Action pipeline & Celery dispatch│
│   8. import_export     : Universal bulk CSV/Excel/JSON mapping & streaming engine       │
│   9. backup            : Disaster recovery CLI & atomic database/filestore bundles     │
│  10. mail_gateway      : Outbound SMTP, inbound mailboxes, Jinja2 templates & queue     │
│  11. notification_engine: Multi-channel push (In-App WebSocket, WebPush, FCM/APNs)     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Powered by
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                           TIER 1: SYSTEM KERNEL (core/)                                │
│   (Pure infrastructure runtime engine; zero business domain logic)                     │
│                                                                                        │
│   - kernel.py          : Module discovery, manifest validator, acyclic DAG resolver    │
│   - database.py        : Async SQLAlchemy engine, session factory & connection pools   │
│   - context.py         : Request contextvar tracking active company_id & user_id       │
│   - base_models.py     : Declarative base model (UUID PK, tenant scoping, SoftDelete)  │
│   - query_engine.py    : Universal Filter & Aggregator AST compiler into parameterized SQL│
│   - event_bus.py       : In-process lifecycle event dispatcher & Redis Pub/Sub bridge  │
│   - app.py             : FastAPI ASGI application factory & central exception router   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Component Responsibilities:

#### **Tier 1: System Kernel (`backend/core/`)**
*Non-domain platform primitives; guarantees stability, tenant isolation, and lifecycle orchestration:*
* **`kernel.py` (Module Engine)**: Scans directories, parses `manifest.py`, validates acyclic dependencies (DAG), and manages the boot lifecycle: `discover` $\rightarrow$ `load` $\rightarrow$ `migrate` $\rightarrow$ `bootstrap`.
* **`database.py` & `context.py` (Multi-Tenancy Engine)**: Maintains the async connection pool (`asyncpg`) and ContextVars. Automatically injects `WHERE company_id = :active_company_id` and `WHERE deleted_at IS NULL` into all queries and creates at the session level.
* **`base_models.py` (Model Foundation)**:
  * `BaseModel`: UUID primary key, `company_id`, audit timestamps (`created_at`, `updated_at`), and actor references (`created_by_id`, `updated_by_id`).
  * `ExtensibleModelMixin`: Adds `custom_fields JSONB DEFAULT '{}'::jsonb` with automatic PostgreSQL GIN indexing.
  * `SoftDeleteMixin`: Provides transparent soft-delete capabilities (`deleted_at: Optional[datetime] = None`, `deleted_by_id: Optional[UUID] = None`) with Kernel auto-filtration and partial unique index support.
  * `ArchivableMixin`: Provides explicit operational archiving (`is_active: bool`).
* **`query_engine.py` (Universal AST Compilers)**:
  * *Universal Filter Compiler*: Compiles nested boolean JSON trees (`AND`/`OR`) into parameterized SQLAlchemy filter clauses.
  * *Universal Aggregator Compiler*: Compiles declarative aggregation specs (`SUM`, `AVG`, `COUNT`, conditional filters, and computed equations) into high-speed PostgreSQL aggregate queries.
* **`event_bus.py` (Event Backbone)**: Catches in-process entity lifecycle mutations (`before_save`, `after_save`, `on_state_change`) and dispatches them to Celery or Redis Pub/Sub.

#### **Tier 2: Core Base Utilities (`backend/modules/base/`)**
*Pre-installed system modules that expose standardized capabilities for domain apps to inherit:*
1. **`identity_rbac`**: Manages `User` (`user_type: "human" | "ai_agent"`), `Group`, `Permission`, and `UserGroupLink`. Enforces model-level capabilities and 3-tier ownership scopes (`GLOBAL`, `TEAM`, `OWN`).
2. **`settings`**: Provides the dynamic configuration store (`ModuleSettings`) and standardized `GET/PATCH /api/v1/{module}/settings` endpoints for all apps.
3. **`lookups`**: Houses normalized lookup models (`Country`, `City`, `Currency`, `UnitOfMeasure`, `TaxType`, `Tag`) and loads initial ISO seed fixtures on installation.
4. **`audit`**: Houses the immutable `AuditLog` table, capturing entity mutation diffs, actor identities, and audit reporting endpoints.
5. **`chatter`**: Manages polymorphic threaded discussions `(res_model, res_id)`, activity logs, email thread synchronization, and team notes.
6. **`documents`**: Attachment manager providing Content-Addressable Storage (`filestore/`) and parent-inherited permission security.
7. **`automated_actions`**: The Trigger-Condition-Action (TCA) engine, orchestrating event rules, expression conditions, Celery execution, and Hermes AI Agent invocations (`invoke_ai_agent`).
8. **`import_export`**: Reusable streaming service for CSV, Excel, and JSON batch processing with dynamic field mapping and validation.
9. **`backup`**: Disaster recovery CLI tools and Celery Beat scheduled jobs producing unified atomic archive bundles (`dump.sql` + `filestore/` + `manifest.json`).
10. **`mail_gateway`**: Outbound SMTP server configurations, inbound mailbox synchronization (IMAP/webhooks), Jinja2 multi-lingual templates, and async queued dispatch with bounce tracking.
11. **`notification_engine`**: Dedicated multi-channel push dispatcher handling In-App WebSocket notifications, Web Push (W3C/VAPID), Mobile Push (FCM/APNs), and per-user delivery preference matrices.

#### **Tier 3: Pluggable Domain Applications (`backend/modules/apps/`)**
*Independent business verticals; each modular app follows a uniform package layout:*
* `manifest.py`: Package name, version, dependencies (`depends_on`), `ai_enabled: bool`, and settings schema ref.
* `models.py`: Business models subclassing Kernel's `BaseModel` (inheriting multi-tenancy, custom fields, and audit timestamps).
* `schemas.py`: Pydantic request/response models with agent-first documentation and realistic examples.
* `routes.py`: FastAPI `APIRouter` mounting into the Kernel API gateway.
* `actions.py`: Domain-specific business logic, state transitions, and automated action definitions.
* `seed.json`: Default initial fixtures specific to the module.

---

## 4. Technology Stack & Runtime (Dimension 2 — AGREED)

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

## 4. Dimension 2: Technology Stack & Runtime (AGREED)

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

## 5. Dimension 3: Database & Multi-Tenant Storage Strategy (AGREED)

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

## 6. Dimension 4: Asynchronous Execution, Task Queue & Event Bus (AGREED)

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

## 7. Dimension 5: Hermes Agent Bridge & MCP Integration (AGREED)

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

## 8. Comprehensive Architectural Blueprint Status

All 5 core dimensions have been collaboratively brainstormed and agreed upon:
* [x] **Dimension 1**: Architecture & Philosophy (18 core principles including contextual RBAC, per-app settings, relational dynamism, i18n, audit logging, first-class AI agent user identity, universal aggregator, bulk import/export, unified atomic backups, multi-channel notification push, and soft-delete integrity).
* [x] **Dimension 2**: Technology Stack (FastAPI, PostgreSQL 16, SQLAlchemy 2.0 Async, Alembic, Redis + Celery, Pydantic v2).
* [x] **Dimension 3**: Database & Multi-Tenant Storage Strategy (Pattern A: Shared DB with `company_id` + `JSONB` custom fields with GIN indexes).
* [x] **Dimension 4**: Asynchronous Execution & Event Bus (ORM hooks $\rightarrow$ Redis/Celery $\rightarrow$ WebSockets + Celery Beat).
* [x] **Dimension 5**: Hermes Agent Bridge & MCP Integration (Configurable Automated Actions with dynamic prompt templates & RBAC gating).

---

## 9. Implementation Roadmap & Milestones

### Milestone 1: Container Infrastructure & Docker Scaffolding
- [ ] Configure `backend`, `postgres:16-alpine`, `redis:7-alpine`, and `celery_worker` services in Docker Compose.
- [ ] Scaffolding Python dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `celery`, `redis`, `pydantic`.
- [ ] Verify health checks and database connectivity inside the isolated Docker network.

### Milestone 2: Micro-Kernel Core & Dynamic Module Loader
- [ ] Implement `backend/core/kernel.py`: dynamic module discovery, manifest validation (`manifest.py`), and acyclic dependency DAG enforcement.
- [ ] Implement Kernel lifecycle management stages: `discover` $\rightarrow$ `load` $\rightarrow$ `migrate` $\rightarrow$ `bootstrap`.

### Milestone 3: Multi-Tenancy, Soft Delete & Database ORM Engine
- [ ] Base SQLAlchemy async declarative model with automatic `company_id` multi-tenancy injection.
- [ ] `SoftDeleteMixin` (`deleted_at`, `deleted_by_id`) with automatic Kernel-enforced query filtration (`WHERE deleted_at IS NULL`) and PostgreSQL partial unique index support.
- [ ] Extensible `custom_fields JSONB` column with PostgreSQL GIN indexing on base entities.
- [ ] FastAPI session middleware enforcing active `company_id` context on all requests.

### Milestone 4: Universal Advanced Filtering & Aggregator Engine
- [ ] Declarative AST parser and compiler for nested boolean query trees (`AND`, `OR`, `NOT`).
- [ ] Parameterized SQLAlchemy query translation with full operator support (`eq`, `contains`, `in`, `between`, relational traversals).
- [ ] Universal Aggregation & Equation Engine: declarative schema compiling `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, multi-level `GROUP BY`, temporal bucketing, conditional filters (`FILTER WHERE`), and computed arithmetic equations.

### Milestone 5: Core Base Utilities (Installed by Default)
- [ ] **Identity & Contextual RBAC**: `User` model with `user_type: "human" | "ai_agent"`, 3-tier ownership scopes (`GLOBAL`, `TEAM`, `OWN`), model-level capabilities, user overrides, and parent-inherited permissions for polymorphic attachments.
- [ ] **Multi-Language (i18n / l10n)**: Request language negotiation (`Accept-Language`), translation catalogs, and `JSONB` multi-lingual field support.
- [ ] **Enterprise Audit Trail**: Immutable `AuditLog` table capturing actor, timestamp, operation, and before/after JSON diffs.
- [ ] **Mail Gateway Subsystem**: Outbound SMTP server management, inbound mailbox sync (IMAP/webhooks), multi-lingual Jinja2 templates, and queued async delivery with bounce tracking.
- [ ] **Multi-Channel Push & Notification Engine**: Dedicated dispatcher for In-App WebSockets, Web Push (W3C/VAPID), Mobile Push (FCM/APNs), and per-user delivery preference matrices.
- [ ] **Universal Import & Export Service**: CSV, Excel, and JSON batch processing with dynamic schema mapping, field validation, async Celery execution, and capability-scoped access.
- [ ] **Per-Module Settings Subsystem**: Scoped module configuration contracts and API endpoints (`GET/PATCH /api/v1/{module}/settings`).
- [ ] **Dynamic Lookups & Seed Fixtures**: Normalized lookup models (countries, currencies, categories) with auto-seeded default data.
- [ ] **Contextual Chatter & WebSockets**: Polymorphic threaded discussions `(res_model, res_id)` with internal notes, emails, and Redis Pub/Sub WebSocket broadcasting.
- [ ] **File & Document Storage**: Attachment manager supporting blob persistence, MIME metadata, and parsing.

### Milestone 6: Event-Driven Automated Actions & Backup Engine (TCA)
- [ ] Trigger registry: ORM lifecycle hooks (`on_create`, `on_update`, `on_delete`, `on_state_change`), Celery Beat cron intervals.
- [ ] Universal condition evaluator running against record attributes and relational paths.
- [ ] Action execution dispatcher: `update_record`, `create_record`, `send_email`, `invoke_webhook`.
- [ ] **Unified Atomic Backup Engine**: Standalone CLI scripts (`backup.sh`, `restore.sh`), atomic archive bundle (`dump.sql` + `filestore/` + `manifest.json`), and scheduled automated backup actions via Celery Beat.

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
  * Atomic backup archive creation and restore integrity.
  * End-to-end Hermes Agent dispatch and chatter callbacks.

---

## 10. Current Focus
All architectural dimensions and structural taxonomies are finalized. Ready for execution of **Milestone 1: Container Infrastructure & Docker Scaffolding**.

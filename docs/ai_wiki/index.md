# AI System Template — System Overview

An extensible, production-grade starter template pairing a **Django** web framework (REST API, Admin, PostgreSQL, Redis) with the autonomous **Nous Research Hermes Agent** execution runtime in Docker, featuring isolated specialist agent profiles, custom skill auditing, and dynamic model catalogs.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `main`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Status**: Phase 17 Completed (Universal Document & Media Management across SHA-256 Checksums, GenericForeignKey Attachments, Secure Token Signer, REST APIs, and Admin Generic Inlines)


---

## Primary System Components

### 1. Backend Service (`backend/`)
- **Framework**: Django 5.x with Django REST Framework on Python 3.11.
- **Data Persistence**: PostgreSQL 16 relational database with Redis 7 caching and session broker.
- **Dynamic Administrative Portal**: Django Admin with single-screen `CustomUserAdmin` embedding `ProfileInline`, dynamic provider/model dropdowns, and a live 🔄 **Reload Profiles** widget.
- **Model Catalog Engine**: Powered by `models.dev` dynamic registry and OpenRouter, rendering live context window length and token pricing cards ($/1M tokens).
- **Core Models**:
  - `Profile`: Unified User Profile model attached 1-to-1 to `auth.User` via automatic `post_save` lifecycle signals, categorizing accounts (`is_agent`, `user_type: human/agent/client`) and managing Hermes AI inference configurations.
  - `AgentTask`: Task execution registry with assigned profiles, execution costs, reasoning overrides, and QA review pipelines.
  - `SpendReport`: Structured token usage and budget status reports emitted by the cost controller.
  - `HandshakeLog`: Audit log of agent container boot and lifecycle handshakes.

### 2. Autonomous Agent Engine (`agent_service/` & Hermes Runtime)
- **Engine**: Nous Research `hermes-agent` running in an isolated Docker container (`hermes-template-agent`).
- **5 Universal Agent Profiles**:
  1. `orchestrator`: Request intake, project decomposition, Kanban routing, and response synthesis (Effort: `medium`).
  2. `cost_controller`: Token consumption tracking, budget cap enforcement, expense auditing (Effort: `low`).
  3. `qa_auditor`: Review pipeline gatekeeper, quality control, output verification (Effort: `high`).
  4. `comms_agent`: Customer communications, email drafting, meeting scheduling, client intake (Effort: `low`).
  5. `archivist`: Documentation maintainer, institutional memory, SOPs, wiki indexing (Effort: `medium`).
- **Execution Mechanism**: Invoked directly via `hermes -p <profile_name> --reasoning <level>`.

### 3. Declarative Profile Provisioning (`scripts/provision_profiles.py`)
- Declarative source definitions in `agent_service/profiles/<name>/` containing `SOUL.md`, `config.yaml`, and `profile.yaml`.
- Automated idempotent provisioning script that registers profiles in Hermes runtime, creates aliases, symlinks personas, and sets default models.

### 4. Custom Foundation Skills (`agent_service/skills/`)
- `cost_monitor`: Directly inspects `session_model_usage` across all profile SQLite `state.db` files, aggregating token expenditure and checking against daily budget caps.
- `output_validator`: Empirical syntax parser (Python AST, JSON), credential leak detector, and placeholder hygiene reviewer for QA gatekeeping.

### 5. Bidirectional API Contract & Review Pipeline
- **Handshake & Health**: Standardized REST endpoints (`POST /api/handshake/`, `GET /api/ping-hermes/`, `GET /api/health/`).
- **Catalog Endpoints**: `GET /api/hermes/providers/`, `GET /api/hermes/models/?provider=<slug>`.
- **Review Pipeline**: Tasks transition across `pending` → `in_progress` → `review` → `completed` / `failed`, reviewed by `qa_auditor` via `POST /api/tasks/<id>/submit-verdict/`.

### 6. Role-Based Access Control (RBAC) & Service Accounts
- **Dedicated Bot Users**: Each profile is linked to a dedicated Django service account (`bot_orchestrator`, `bot_cost_controller`, `bot_qa_auditor`, `bot_comms_agent`, `bot_archivist`) with unusable passwords.
- **Native Django Groups**: Mapped to granular model permissions (`add`, `change`, `view`, `delete`) enforcing the Principle of Least Privilege.
- **Strict DRF Authentication**: All data-modifying endpoints require `TokenAuthentication` and `StrictDjangoModelPermissions` (e.g. only `cost_controller` can ingest spend reports; only `qa_auditor` can submit task review verdicts).
- **Runtime Credential Propagation**: Automatically synced into Hermes profile directories (`/root/.hermes/profiles/<name>/.env`) via `scripts/provision_profiles.py`.

### 7. Unified User Profile & Live Engine Discovery
- **Single-Screen User Management**: `CustomUserAdmin` embeds `ProfileInline` directly in the `auth.User` change form, managing credentials, RBAC groups, and AI settings seamlessly.
- **Visual Classification Badges**: User list table features distinct badges: `🤖 Agent (profile_slug)`, `👤 Staff`, `🌐 Client`.
- **Live Hermes Discovery Service**: Scans mounted declarative profile definitions (`/app/agent_profiles/`) and provides the `GET /api/hermes/profiles/` endpoint.
- **Dynamic 🔄 Reload Widget**: Admin interface features an asynchronous button that live-refreshes available engine profiles into the `<select>` dropdown without page reload, automatically populating canonical roles and descriptions.

### 8. Centralized Automation Engine & Distributed Task Queue (`apps.automation`)
- **Distributed Queue**: Celery 5.4+ with Redis 7 message broker and `django-celery-beat` database scheduler running in isolated worker (`celery_worker`) and scheduler (`celery_beat`) containers.
- **Dynamic Service Registry**: 4 distinct service categories (`hermes_agent`, `internal_app`, `script_service`, `external_webhook`) with decorator-based registration (`@register_action`).
- **Dynamic Introspection API**: REST endpoint `GET /api/automation/introspection/?model=...` providing real-time schema field types, requirement constraints, and choices.
- **Next-Gen Odoo-Style Target Operations**: Semantic separation of `trigger_model` (source event) vs `target_model` (destination record operations), executing automated `create`, `update`, and `delete` actions with template context interpolation (`{{var}}`).
- **Visual Condition Rules**: Declarative operator evaluation (`==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `in`, `is_empty`, `is_not_empty`) and Odoo-style state transition monitoring (`trigger_field`, `previous_value`, `target_value`).
- **System Signal Reification**: Foundational routines (Hermes auto-provisioning, spend audit, QA review routing, budget alert) marked `is_system=True` and locked against deletion in models and Admin.
- **Reactive Dynamic Admin UI**: Conditional section toggling, live AJAX field introspection, interactive field mapping assistant with required field badges, and visual boolean filter group builders.
- **Direct On-Page Execution & Context Builder**: On-demand `▶ Run Pipeline Now` and `▶ Run Action Now` execution buttons on change forms and changelists, backed by dynamic database context resolution, sensible fallback synthesis, and `force_execution` testing bypasses.
- **Hermes Gateway Resilience**: Standardized token authentication, configurable execution timeouts (`HERMES_REQUEST_TIMEOUT = 120s`), and automated action deduplication.

### 9. Core Foundations, Modular App Settings & Multi-Language Engine (`apps.core`)
- **Abstract Base Models**:
  - `TimeStampedModel`: Standardized indexed `created_at` and `updated_at`.
  - `UUIDModel`: Distributed, non-enumerable `id = UUIDField(primary_key=True, default=uuid.uuid4)`.
  - `SoftDeleteModel`: Paranoid soft-deletion model with dual managers (`objects.alive()` vs `all_objects`) and `.restore()` method.
  - `AuditableModel`: Contextvars-driven request user tracking auto-populating `created_by` and `updated_by`.
- **Odoo-Style Modular Application Settings Framework**:
  - **Declarative App Registration**: Each app defines its settings in `conf.py` using `@register_settings_group` with typed definitions (`int`, `str`, `float`, `bool`, `choice`, `secret`, `json`).
  - **Tamper-Proof Secret Encryption**: Dedicated `crypto.py` utilities encrypting and signing sensitive credentials with masking in the admin UI.
  - **High-Speed Dual-Layer Resolution**: `get_setting("app.KEY", default=...)` with sub-millisecond Redis caching, database persistence, and automatic cache invalidation.
  - **Unified Settings Hub**: Single-screen configuration dashboard in Django Admin with categorized app sidebar navigation.
- **Bilingual Multi-Language Engine (English / Arabic)**:
  - Full i18n & l10n pipeline via `LocaleMiddleware`, compiled `.mo` catalogs, and native Arabic RTL typography.
  - User profile `preferred_language` on `Profile` model with dynamic admin language switcher.

### 10. Metadata Engine, Dynamic Schema & Modular App Runtime (`apps.meta_engine`)
- **Metadata Catalog Models**:
  - `SystemModule`: Odoo-style app package registry tracking metadata, versions, dependencies, and installed status.
  - `MetaModel` & `MetaField`: Declarative business entity catalog supporting 12 data types, relational links, and reserved keyword protection.
  - `MetaView`, `MetaMenu`, `MetaAction`, `MetaRule`, `MetaReport`: Declarative form/list/kanban layout schemas, hierarchical menus, actions, row-level domain security rules, and printable CSS Paged Media reports.
- **Dynamic PostgreSQL Schema Engine (`DynamicSchemaEngine`)**:
  - Direct PostgreSQL DDL execution via Django's `SchemaEditor`: creates tables, adds/alters columns, creates indexes, and links foreign keys dynamically without manual migrations or server reboots.
  - Database lifecycle signals in `signals.py` auto-sync physical schema on metadata changes.
- **Dynamic In-Memory Model Factory (`DynamicModelFactory`)**:
  - Compiles live, in-memory Django models inheriting `(UUIDModel, SoftDeleteModel, AuditableModel)` registered directly into `django.apps.apps`.
  - Supports standard Django ORM operations (`filter`, `create`, `save`, `delete`, joins) and paranoid soft deletion.
- **Modular App System & Lifecycle**:
  - `AppManifestReader`: Discovers and parses `manifest.json` packages on disk and syncs them to the database.
  - `DependencyResolver`: Directed acyclic graph (DAG) topological dependency resolution and cycle detection.
  - `AppInstaller`: Multi-pass ingestion engine (Models -> Relational Links -> Views -> Menus -> Actions -> Reports).
  - `AppUninstaller`: Safe uninstallation engine with reverse dependency validation guard and 3 data retention policies (`archive`, `snapshot_backup_and_drop`, `cascade_drop`).
- **Universal Declarative REST API Gateway**:
  - Polymorphic REST endpoints (`/api/v1/entities/<model_slug>/`) with dynamic serializers, filtering, pagination, search, and row-level `MetaRule` domain security.
  - Declarative schema introspection endpoint (`/api/v1/entities/<model_slug>/schema/`).
- **Odoo-Style Admin App Store & Studio UI**:
  - Visual App Store dashboard (`/admin/meta_engine/systemmodule/app-store/`) with 1-click install, uninstall with data retention policies, and disk synchronization.
  - Dynamic PostgreSQL DDL status badges and API gateway navigation directly in Django Admin.

### 12. Multi-Tenancy, Organizations & Workspaces (`apps.tenants`)
- **Tenant Hierarchy & RBAC Memberships**:
  - `Organization`: Tenant entity managing workspaces, subscription tiers (`free`, `starter`, `pro`, `enterprise`), max user capacity, custom domains, and JSON metadata.
  - `OrganizationMembership`: Junction associating users with workspaces under role-based membership (`owner`, `admin`, `member`, `viewer`, `guest`).
  - `OrganizationInvitation`: Expiring tokenized email invitations with self-service acceptance lifecycle.
- **Row-Level Tenant Isolation**:
  - `TenantAwareModel`: Abstract base model with indexed foreign key to `Organization` and automated context binding on save.
  - `TenantManager` & `TenantQuerySet`: Automatic query scoping with integrated soft-delete support (`alive()`, `dead()`, `restore()`, `hard_delete()`).
  - `TenantAllManager`: Explicit unfiltered access for migrations, global analytics, and superuser maintenance.
- **Thread-Safe Context & Multi-Strategy Middleware**:
  - Python 3.11 `contextvars` context manager (`tenant_context(org)`, `bypass_tenant_isolation()`).
  - `TenantMiddleware`: Resolves active workspace from HTTP headers (`X-Workspace-Slug`, `X-Organization-ID`), query parameters (`?workspace=`), host domains/subdomains, user default active memberships, and the global fallback default workspace.
- **Declarative Dynamic Engine Integration**:
  - `MetaModel.is_tenant_aware` flag compiling in-memory dynamic models with `TenantAwareModel` base class and physical PostgreSQL `organization_id` foreign key column.
  - Dynamic REST API Gateway (`/api/v1/entities/<model_slug>/`) auto-scopes records and auto-binds tenant foreign keys upon creation.
- **REST APIs & Admin Site**:
  - `OrganizationViewSet` (`/api/v1/organizations/`): CRUD for organizations, member listing/adding, invitation creation, and workspace switching.
  - `InvitationAcceptAPIView` (`/api/v1/invitations/<token>/accept/`): Secure invitation token acceptance endpoint.
  - Full Django Admin with inline member management, active seat counters, and tier badges.

### 13. Comprehensive Activity Audit Trail (`apps.audit`)
- **Universal Immutable Audit Log (`ActivityLog`)**:
  - Captures events across human users, bot service accounts, and system background processes for compliance (SOC2, GDPR, ISO 27001).
  - Built on `GenericForeignKey` (`content_type` and string `object_id`), seamlessly supporting both Integer PK models (`auth.User`, `AppSettingValue`) and UUID PK models (`Organization`, `MetaModel`, dynamic entities).
  - Multi-tenant scoping with nullable `organization` foreign key, allowing both tenant-isolated and global system events.
  - Strict immutability: updates and deletes blocked on both instance (`save()`, `delete()`) and bulk QuerySet (`update()`, `delete()`) levels unless explicitly authorized with `allow_purge=True`.
- **Request Context & Client Telemetry Middleware (`AuditContextMiddleware`)**:
  - Extracts client IP (`X-Forwarded-For`, `X-Real-IP`, `REMOTE_ADDR`), User-Agent, and correlation ID (`X-Request-ID`).
  - Binds parameters to Python 3.11 `contextvars` (`apps.audit.context`) with guaranteed token cleanup in a `finally` block and injects `X-Request-ID` into response headers.
- **Automated Lifecycle Diffing & Security Signals (`apps.audit.signals`)**:
  - Listens to `pre_save`, `post_save`, and `post_delete` signals to calculate structured attribute diffs (`{"field": {"old": v1, "new": v2}}`).
  - Smart noise suppression: ignores auto-timestamps (`updated_at`), masks sensitive fields (`password`, `token`, `secret`), and suppresses logs when no attributes actually change.
  - Tracks state transitions: soft deletes (`ACTION_DELETE`), restores (`ACTION_RESTORE`), and permanent deletions (`ACTION_HARD_DELETE`).
  - Security authentication event logging: `user_logged_in`, `user_logged_out`, and `user_login_failed`.
- **Declarative Dynamic Model Integration**:
  - Seamlessly integrates with `apps.meta_engine` (`meta_model.is_auditable=True`), auto-registering in-memory models and tracking CRUD operations.
- **Read-Only Admin Dashboard & REST API Gateway**:
  - Read-only Django Admin (`ActivityLogAdmin`) with formatted visual before/after HTML diff cards and colored status/action badges.
  - Read-only REST API (`/api/v1/audit/logs/`) with multi-tenant filtering, search, and action parameter filters.

### 14. Universal Notifications Engine (`apps.notifications`)
- **Notification Data Models**:
  - `Notification`: Inherits `TenantAwareModel` and `SoftDeleteModel`. Multi-tenant workspace notification record supporting levels (`info`, `success`, `warning`, `error`), recipient, actor (User/Bot), action URLs, read status, channel (`in_app`, `email`, `webhook`, `slack`, `hermes`), and JSON metadata payload.
  - `NotificationPreference`: Per-user multi-channel toggles (`in_app`, `email`, `webhook`, `slack`) and webhook/Slack destination endpoints.
- **Real-Time Dispatcher & Multi-Channel Adapters (`dispatcher.py`)**:
  - `NotificationDispatcher`: Central manager for preference resolution, channel filtering, and adapter invocation.
  - Multi-channel adapters (`InAppAdapter`, `EmailAdapter`, `WebhookAdapter`, `SlackAdapter`).
  - Redis unread counter management (`notifications:unread_count:{user_id}:{org_id}`) with automatic signal invalidation.
- **Asynchronous Celery Tasks (`tasks.py`)**:
  - `send_notification_async_task`: Non-blocking background worker task with exponential backoff retries.
- **Automation Engine Integration (`apps.automation.actions`)**:
  - Registered flagship action `@register_action("send_notification", ...)` allowing system triggers to fire notifications automatically.
- **REST API Gateway & Django Admin**:
  - DRF ViewSets (`/api/v1/notifications/`, `/mark-read/`, `/mark-all-read/`, `/unread-count/`, `/preferences/`).
  - Colored Django Admin badges and bulk `mark_selected_as_read` actions.

### 15. Universal Document & Media Management (`apps.media`)
- **Document Data Model**:
  - `Document`: Inherits `TenantAwareModel` and `SoftDeleteModel`. Multi-tenant workspace file attachment model featuring SHA-256 checksums (`checksum_sha256`), automatic MIME detection, size formatting (`1.5 MB`), `uploaded_by`, and `is_public` flags.
  - `GenericForeignKey` (`content_type` + `object_id`): Enables seamless attachment linking to any system model (`AgentTask`, `User`, `Organization`, etc.).
- **Pluggable Storage & Secure Token Signer (`storage.py` & `services.py`)**:
  - `SecureDocumentStorage`: Partitioned directory structure (`/app/media/documents/<org_id>/<sha256[:2]>/<sha256>_<filename>`).
  - Cryptographically signed URL generator (`generate_secure_download_token`) with time-limited expiration (`TimestampSigner`).
  - `MediaService`: Centralized file ingestion, SHA-256 calculation, and permission-checked `FileResponse` binary streaming.
- **REST API Gateway & Django Admin**:
  - DRF ViewSet (`/api/v1/media/documents/upload/`, `/download/`).
  - `DocumentAdmin` with monospaced SHA-256 badges and human size formatters.
  - Reusable `GenericDocumentInline` component embeddable in any admin model change form.







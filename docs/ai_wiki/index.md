# AI System Template — System Overview

An extensible, production-grade starter template pairing a **Django** web framework (REST API, Admin, PostgreSQL, Redis) with the autonomous **Nous Research Hermes Agent** execution runtime in Docker, featuring isolated specialist agent profiles, custom skill auditing, and dynamic model catalogs.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `main`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Agent Team Reference**: [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md)
- **Status**: Phase 24 Completed (LLM Model Modalities, Visual Capability Badges & Dropdown Indicators; 100% test pass rate across 185 tests)

---

## Primary System Components


### 1. Backend Service (`backend/`)
- **Framework**: Django 5.x with Django REST Framework on Python 3.11.
- **Data Persistence**: PostgreSQL 16 relational database with Redis 7 caching and session broker.
- **Dynamic Administrative Portal**: Django Admin with single-screen `CustomUserAdmin` embedding `ProfileInline`, `ProviderCredentialAdmin` with masked secret widgets, visual Settings Hub banner in `AppSettingValue`, dynamic provider/model dropdowns with compact modality badges (`[🖼️ Vision]`, `[📁 PDF]`, `[🎙️ Audio]`, `[🎥 Video]`, `[💬 Text]`), and a live 🔄 **Reload Profiles** widget.
- **Model Catalog Engine**: Powered by `models.dev` dynamic registry and OpenRouter, rendering live context window length, token pricing cards ($/1M tokens), and normalized input/output modality chips (`Text`, `Vision/Image`, `Document/PDF`, `Audio/Voice`, `Video`).

- **Core Models**:
  - `ProviderCredential`: Encrypted storage for LLM provider API keys (OpenRouter, Gemini, OpenAI, Anthropic, Groq, DeepSeek) with multi-tenant scoping and masked admin representation.
  - `Profile`: Unified User Profile model attached 1-to-1 to `auth.User` via automatic `post_save` lifecycle signals, categorizing accounts (`is_agent`, `user_type: human/agent/client`), managing Hermes AI inference configurations, and hierarchical key resolution (`resolve_provider_and_key()`).
  - `AgentTask`: Task execution registry with assigned profiles, execution costs, reasoning overrides, and QA review pipelines.
  - `SpendReport`: Structured token usage and budget status reports emitted by post-execution hooks and cost controllers.
  - `HandshakeLog`: Audit log of agent container boot and lifecycle handshakes.

### 2. Autonomous Agent Engine (`agent_service/` & Hermes Runtime)
- **Engine**: Nous Research `hermes-agent` running in an isolated Docker container (`hermes-template-agent`).
- **Zero-Downtime Credential Sync**: Hermes dynamically loads per-profile secret scopes on each turn (`build_profile_secret_scope`). Django volume-mounts (`/app/hermes_runtime_data` and `/app/hermes_root_env`) allow immediate credential synchronization on `post_save` with 0 downtime and no container restarts.
- **5 Calibrated Agent Profiles**:
  1. `orchestrator`: Request intake, project decomposition, Kanban routing, and response synthesis (Calibrated Effort: `none` for instant triage).
  2. `cost_controller`: Token consumption tracking, budget cap enforcement, expense auditing (Calibrated Effort: `low`).
  3. `qa_auditor`: Review pipeline gatekeeper, quality control, output verification (Calibrated Effort: `high`).
  4. `comms_agent`: Customer communications, email drafting, meeting scheduling, client intake (Calibrated Effort: `none` for fast client replies).
  5. `archivist`: Documentation maintainer, institutional memory, SOPs, wiki indexing (Calibrated Effort: `low`).
- **Execution Mechanism**: Invoked directly via `hermes -p <profile_name> --reasoning <level>` or over Gateway HTTP `/v1/chat/completions`.

### 3. Declarative Profile Provisioning (`scripts/provision_profiles.py`)
- Declarative source definitions in `agent_service/profiles/<name>/` containing `SOUL.md`, `config.yaml`, and `profile.yaml`.
- Automated idempotent provisioning script that registers profiles in Hermes runtime, creates aliases, symlinks personas, and sets default models.


### 4. Specialist Profile Skills & Shared System Skills
- **Profile-Scoped Skills (`agent_service/profiles/<name>/skills/`)**:
  - `task_decomposer` (scoped to `orchestrator`): Directed acyclic graph (DAG) objective decomposition, dependency validation, cycle detection, and automated Django task submission (`POST /api/tasks/`).
  - `cost_monitor` (scoped to `cost_controller`): Inspects `session_model_usage` across profile SQLite `state.db` files, aggregating token expenditure and checking daily budget caps.
  - `output_validator` (scoped to `qa_auditor`): Empirical syntax parser (Python AST, JSON, YAML), credential leak detector, and placeholder hygiene reviewer for the QA review gate.
- **Skill Pruning & Token Efficiency**:
  - Profiles opt out of Hermes's 54 bundled skills (games, media, audio, deep debugging) via the `.no-bundled-skills` marker, saving thousands of prompt tokens per turn and focusing execution on dedicated capabilities.
- **Shared System Skills (`agent_service/skills/`)**:
  - `django_handshake`: System bootstrap skill verifying cross-container reachability, handshake registration (`POST /api/handshake/`), and database audit persistence.

### 5. Bidirectional API Contract & Review Pipeline
- **Handshake & Health**: Standardized REST endpoints (`POST /api/handshake/`, `GET /api/ping-hermes/`, `GET /api/health/`).
- **Catalog Endpoints**: `GET /api/hermes/providers/`, `GET /api/hermes/models/?provider=<slug>`.
- **Review Pipeline**: Tasks transition across `pending` → `in_progress` → `review` → `completed` / `failed`, reviewed by `qa_auditor` via `POST /api/tasks/<id>/submit-verdict/`.

### 6. Role-Based Access Control (RBAC) & Service Accounts
- **Dedicated Bot Users**: Each profile is linked to a dedicated Django service account (`bot_orchestrator`, `bot_cost_controller`, `bot_qa_auditor`, `bot_comms_agent`, `bot_archivist`) with unusable passwords.
- **Native Django Groups**: Mapped to granular model permissions (`add`, `change`, `view`, `delete`) enforcing the Principle of Least Privilege.
- **Strict DRF Authentication**: All data-modifying endpoints require `TokenAuthentication` and `StrictDjangoModelPermissions` (e.g. only `cost_controller` can ingest spend reports; only `qa_auditor` can submit task review verdicts).
- **Runtime Credential Propagation**: Automatically synced into Hermes profile directories (`/root/.hermes/profiles/<name>/.env`) via `scripts/provision_profiles.py`.

### 7. Unified User Profile, Live Engine Discovery & Dynamic Model Specifications
- **Single-Screen User Management**: `CustomUserAdmin` embeds `ProfileInline` directly in the `auth.User` change form, managing credentials, RBAC groups, and AI settings seamlessly.
- **Visual Classification Badges**: User list table features distinct badges: `🤖 Agent (profile_slug)`, `👤 Staff`, `🌐 Client`.
- **Live Hermes Discovery Service**: Scans mounted declarative profile definitions (`/app/agent_profiles/`) and provides the `GET /api/hermes/profiles/` endpoint.
- **Dynamic 🔄 Reload Widget**: Admin interface features an asynchronous button that live-refreshes available engine profiles into the `<select>` dropdown without page reload, automatically populating canonical roles and descriptions.
- **Dynamic Modality Badges & Specifications Card (`agent_profile_models.js`)**:
  - Live model dropdowns grouped by vendor (`<optgroup>`) with compact modality indicators (`[🖼️ Vision]`, `[💬 Text]`, `[📁 PDF]`, `[🎙️ Audio]`, `[🎥 Video]`).
  - Interactive, full-width specifications card (`.hermes-model-specs-card`) displaying context window, token input/output pricing, accepted input and generated output modality badges, and reasoning badges directly below the model selector without clipping.
  - Compatible with both `CustomUserAdmin` (inline) and standalone `ProfileAdmin`, with cache-busting query strings (`?v=24.1`).

### 8. Centralized Automation Engine & Distributed Task Queue (`apps.automation`)
- **Distributed Queue**: Celery 5.4+ with Redis 7 message broker and `django-celery-beat` database scheduler running in isolated worker (`celery_worker`) and scheduler (`celery_beat`) containers.
- **Sequential Pipeline Chaining & Context Passing**: Coordinates multi-action execution (`sequence=10, 20...`) sequentially within `execute_pipeline`, passing mutated context forward (e.g. `record_id` created in Step 1 is dynamically available in Step 2) with `stop_on_failure` circuit breaking.
- **Transaction-Safe Signal Dispatch**: Dispatches model event pipelines via `transaction.on_commit` in production to prevent Celery worker race conditions on uncommitted records.
- **Cascading Recursion & Infinite Loop Guard**: Context-variable tracked `_automation_depth` with strict `MAX_AUTOMATION_DEPTH = 3` ceiling preventing circular trigger cascades.
- **Multi-Tenant Workspace Scoping**: Optional `organization` FK on triggers, actions, and logs, isolating tenant automations and executing tasks within `tenant_context`.
- **Target Model CRUD Sandboxing**: Blacklist preventing automated modifications against internal framework tables (`auth.Permission`, `authtoken.Token`, `sessions.Session`, etc.).
- **Dynamic Introspection API & Service Registry**: 4 distinct service categories with `@register_action`, parameter schema validators, prompt presets, and live model field introspection (`GET /api/automation/introspection/`).
- **Reactive Dynamic Admin UI & Direct Execution**: Conditional section toggles, visual boolean filter group builders, workspace badges, and on-demand `▶ Run Pipeline Now` / `▶ Run Step` controls, and automated action deduplication.

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

### 16. Developer API Gateway, Scoped Keys & Inbound Webhooks (`apps.api_gateway`)
- **Data Models (`models.py`)**:
  - `APIKey`: Cryptographically hashed secret key model (`prefix`, `hashed_key` SHA-256 digest, `scopes` list, `allowed_ips` list, `expires_at`, `is_active`, `last_used_at`). Raw keys generated once (`agy_live_<hex>`) and never stored in plain text.
  - `InboundWebhook`: Configurations for third-party SaaS webhook ingestion (`name`, `endpoint_slug`, `secret_token`, `provider: github/stripe/slack/custom`, `is_active`).
  - `WebhookEvent`: Immutable audit log archiving received payload bodies, headers, status (`pending`, `processed`, `failed`), and error tracebacks.
- **DRF Authentication Provider (`authentication.py`)**:
  - `APIKeyAuthentication`: DRF authentication class checking `X-API-Key` or `Authorization: Api-Key <raw_key>` headers, matching 12-char prefix, verifying SHA-256 hash digest, checking expiration and IP allowlists, setting active tenant context on request, and updating `last_used_at`.
- **HMAC Signature Verification Engine (`signature.py`)**:
  - `verify_hmac_signature`: Supports GitHub (`X-Hub-Signature-256`), Stripe (`Stripe-Signature` timestamped), Slack (`X-Slack-Signature`), and custom HMAC SHA-256 providers.
### 17. Dynamic Visual Reporting & PDF Generation Engine (`apps.reports`)
- **Data Models (`models.py`)**:
  - `ReportTemplate`: Multi-tenant, soft-deletable document template specification supporting Jinja2/Django HTML compilation, visual layout schemas (`layout_schema`), CSS `@page` media rules, page formats (`A4`, `Letter`, `thermal_80mm`), orientations (`portrait`, `landscape`), and running headers/footers.
  - `ReportExecutionLog`: Audit log tracking template rendering duration (`duration_ms`), output format (`html`/`pdf`), requesting actor, file size, status (`success`/`failed`), and generated `Document` attachments.
- **Rendering & Conversion Engine (`engine.py`)**:
  - `ReportEngine`: HTML template compiler with model introspection token bridge (`get_model_tokens`), WeasyPrint vector PDF rendering (`render_pdf`), and automatic Arabic RTL typography detection (`dir="rtl" lang="ar"`).
- **REST API Gateway & Django Admin**:
  - Template ViewSet: `/api/v1/reports/templates/`, `/preview/` (interactive HTML), `/render/` (vector PDF binary download), `/tokens/` (introspected model tokens).
  - Execution Log ViewSet: `/api/v1/reports/logs/`.
  - Django Admin integration with changeform actions for `▶ Preview HTML` and `▶ Render PDF`.
- **Automation Engine Bridge (`actions.py`)**:
  - Registered `@register_action("generate_pdf_report", ...)` action allowing system triggers to compile PDF reports, store them in `apps.media`, and notify requesting actors.









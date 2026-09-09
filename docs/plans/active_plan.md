# Implementation Plan: Universal AI System Template & Agent Ecosystem

- **Status**: IN_PROGRESS <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `feat/centralized-automation-engine`
- **Last Updated**: 2026-09-09 06:03:00+03:00

---

## Phase 1: Universal Django + Hermes Agent Starter Template (COMPLETED)

### 1. Objective & Scope
Build a clean, domain-agnostic starter template integrating Django (backend + admin + DRF API) and Hermes Agent in **two separate, isolated Docker environments** for security, with PostgreSQL, Redis, and a verified bidirectional connection handshake. Provide a unified, beautifully styled one-click installer (`install.sh`).

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Wiki Initialization, Git Repo & Environment Scaffolding** - COMPLETED (Commit: `d3b3432`)
- [x] **Sub-task 2: Decoupled Docker Compose Scaffolding (Separate Environments)** - COMPLETED (Commit: `a78c65f`)
- [x] **Sub-task 3: Django Backend Core & Handshake API** - COMPLETED (Commit: `a78c65f`)
- [x] **Sub-task 4: Hermes Agent Configuration & Handshake Skill** - COMPLETED (Commit: `a78c65f`)
- [x] **Sub-task 5: Verification & End-to-End Handshake Execution** - COMPLETED (Commit: `475be75`)
- [x] **Sub-task 6: Unified Beautiful One-Click Installer (`install.sh`)** - COMPLETED (Commit: `f7057d7`)

### 3. Key Decisions & Deviations (Phase 1)
- *2026-09-08*: Pivoted from specific domain (economy editor) to a generic starter template (`ai_system_template`) as requested by the user.
- *2026-09-08*: **Security Isolation Pivot**: Split infrastructure into two separate Docker Compose projects (`backend/docker-compose.yml` and `agent_service/docker-compose.yml`) so Django/PostgreSQL and Hermes run in completely isolated container networks with zero shared privileges, communicating strictly over HTTP REST API.
- *2026-09-08*: Defaulted Hermes host port to `8643` (mapping internally to `8642`) to prevent collisions with existing host daemons.
- *2026-09-08*: Verified bidirectional connectivity: Hermes container successfully registered with Django via `http://host.docker.internal:8000/api/handshake/` (stored in PostgreSQL), and Django reverse-pinged Hermes Gateway daemon.
- *2026-09-08*: GitHub PAT permissions updated to Read/Write, all code successfully pushed to `devalees/ai_system_template`.
- *2026-09-08*: Built and verified `install.sh` providing a rich, animated CLI deployment interface with diagnostics, automated health checks, and service summary dashboard.

---

## Phase 2: 5 Universal Core Agent Profiles (COMPLETED)

### 1. Objective & Scope
Design, configure, and integrate 5 universal, domain-agnostic agent profiles into the Hermes Agent environment and Django backend. These profiles act as permanent "department heads" with distinct personas (`SOUL.md`), toolsets, model configurations, and skills, capable of dispatching tasks and spawning ephemeral sub-agents:

1. `orchestrator`: Request intake, project decomposition, Kanban routing, and response synthesis.
2. `cost_controller`: Token consumption tracking, budget cap enforcement, expense auditing.
3. `qa_auditor`: Review pipeline gatekeeper, quality control, output verification (`request-changes` / `approve`).
4. `comms_agent`: Customer communications, email drafting, meeting scheduling, client intake.
5. `archivist`: Documentation maintainer, institutional memory, SOPs, wiki indexing.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branch Initialization (`feat/core-agent-profiles`)** - COMPLETED (Branch created)
- [x] **Sub-task 2: Declarative Profile Definitions (`agent_service/profiles/`)** - COMPLETED (Commit: `0d219b6`)
- [x] **Sub-task 3: Automated Profile Provisioning Script (`scripts/provision_profiles.py`)** - COMPLETED (Commit: `1f09b23`)
- [x] **Sub-task 4: Foundation Skills for Specialist Profiles (`agent_service/skills/`)** - COMPLETED (Commit: `83e6d73`)
- [x] **Sub-task 5: Django Backend Profile Integration & Task Registry (`backend/apps/integration/`)** - COMPLETED (Commit: `80d4478`)
- [x] **Sub-task 6: End-to-End Verification & Documentation Synchronization** - COMPLETED (Commit: `c7c2823`)
- [x] **Sub-task 7: Agent Profile Reasoning Effort Integration & Hermes Runtime Propagation** - COMPLETED (Commit: `3a73252`)

### 3. Key Decisions & Deviations (Phase 2)
- *2026-09-08*: Created branch `feat/core-agent-profiles`.
- *2026-09-08*: Profiles defined declaratively in `agent_service/profiles/<name>/` with dedicated `SOUL.md`, `config.yaml`, and `profile.yaml` for each of the 5 roles (`orchestrator`, `cost_controller`, `qa_auditor`, `comms_agent`, `archivist`).
- *2026-09-08*: Formally clarified in global workflow rules that `active_plan.md` is cumulative and append-only across all project phases.
- *2026-09-08*: Committed and pushed Sub-task 2 (Commit: `0d219b6`).
- *2026-09-08*: Implemented `scripts/provision_profiles.py` with cross-environment execution support (host & container), successfully provisioned all 5 profiles into Hermes runtime, and empirically verified persona inference on OpenRouter with `google/gemini-2.5-flash` (Commit: `1f09b23`).
- *2026-09-08*: Built and verified specialist foundation skills: `cost_monitor` (real-time token accounting & budget status across all profile SQLite databases) and `output_validator` (empirical syntax, hygiene, and security audit for the QA review gate) (Commit: `83e6d73`).
- *2026-09-08*: Implemented Django backend profile integration: added `AgentProfile`, `SpendReport`, and review pipeline on `AgentTask`. Applied migration `0002_agentprofile_agenttask_cost_usd_and_more`, added `seed_profiles` command, updated Django Admin and DRF ViewSets. In response to user direction, reordered `provider` before `model_name` as dependent dropdowns in Django Admin. Upgraded `hermes_catalog.py` to utilize the live multi-provider `models.dev` registry (identical to Hermes Agent CLI), unlocking all contemporary 2026 models for Anthropic, OpenAI, Google Gemini, DeepSeek, xAI, Groq, and Nous Portal. Verified with 7/7 passing unit tests (Commit: `80d4478`).
- *2026-09-08*: Verified end-to-end execution: tested reverse container reachability (`/api/ping-hermes/`), validated profile persona execution in container runtime via `hermes -p <profile>`, and synchronized architecture documentation in `docs/ai_wiki/index.md` and `docs/ai_wiki/architecture.md` (Commit: `69196cc`).
- *2026-09-09*: Added reasoning effort configuration (`reasoning_effort`: `none`, `low`, `medium`, `high`, `max`) to `AgentProfile` and `AgentTask` in Django backend and declarative profile configs (`agent_service/profiles/*/config.yaml`), leveraging Hermes Agent's native `VALID_REASONING_EFFORTS`, `clamp_effort()` safety wire, and `--reasoning` CLI runtime flag. Applied migration `0003_agentprofile_reasoning_effort_and_more`, seeded profiles, updated admin UI with live reasoning capability badge, and verified with 8/8 passing tests.

---

## Phase 3: Django Native RBAC, Service Accounts & Agent Token Authentication (COMPLETED)

### 1. Objective & Scope
Integrate Django's native authentication framework, Role-Based Access Control (`auth.Group` and `auth.Permission`), and Django REST Framework (DRF) Token Authentication to secure agent-to-backend database operations under the Principle of Least Privilege:
- Pair each of the 5 agent profiles with a dedicated Django `User` (Service Account / Bot User: `bot_<profile_name>`).
- Define native Django Groups (`Agent_Orchestrator`, `Agent_CostController`, `Agent_QAAuditor`, `Agent_CommsAgent`, `Agent_Archivist`) with fine-grained model permissions (`add`, `change`, `view`, `delete`).
- Enforce DRF `TokenAuthentication` and model permissions on all database-modifying endpoints.
- Synchronize API tokens to Hermes Agent profile `.env` runtimes via automated provisioning.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Backend Auth Dependencies & Model Extensions** - COMPLETED (Commit: `e332042`)
- [x] **Sub-task 2: Automated RBAC Groups, Bot Users & Token Generation (`seed_profiles.py`)** - COMPLETED (Commit: `c312146`)
- [x] **Sub-task 3: DRF Views Authorization & Endpoint Security Hardening** - COMPLETED (Commit: `8a155ee`)
- [x] **Sub-task 4: Hermes Agent Runtime Token Provisioning (`scripts/provision_profiles.py`)** - COMPLETED (Commit: `8a155ee`)
- [x] **Sub-task 5: Comprehensive Unit Testing & End-to-End Verification** - COMPLETED (Commit: `8a155ee`)
- [x] **Sub-task 6: Documentation Synchronization (Wiki & Architecture)** - COMPLETED (Commit: `cb0b13d`)

### 3. Key Decisions & Deviations (Phase 3)
- *2026-09-09*: Initialized Phase 3 on branch `feat/agent-rbac-service-accounts`. Standardized bot username prefix `bot_<profile_name>` and group prefix `Agent_<Role>`.
- *2026-09-09*: Installed `rest_framework.authtoken`, configured TokenAuthentication and SessionAuthentication in `settings.py`, and added `user` OneToOneField to `AgentProfile`, `created_by` ForeignKey to `AgentTask` and `SpendReport`. Applied migration `0004_agentprofile_user_agenttask_created_by_and_more` (Commit: `e332042`).
- *2026-09-09*: Enhanced `seed_profiles.py` to idempotently construct Django Groups (`Agent_Orchestrator`, `Agent_CostController`, `Agent_QAAuditor`, `Agent_CommsAgent`, `Agent_Archivist`) with native model permissions (`add`, `change`, `view`), generate dedicated `bot_*` users with unusable passwords, issue DRF tokens, and export token manifests via `--export-tokens` (Commit: `c312146`).
- *2026-09-09*: Implemented `StrictDjangoModelPermissions` on ViewSets to enforce RBAC across all HTTP verbs (`view` on GET, `add` on POST, `change` on PUT/PATCH, `delete` on DELETE). Enforced dedicated review gate authorization on `submit_verdict` requiring `Agent_QAAuditor` membership and `change_agenttask` permission. Overrode `perform_create` on `AgentTaskViewSet` and `SpendReportViewSet` to automatically record `created_by` audit trail (Commit: `8a155ee`).
- *2026-09-09*: Upgraded `scripts/provision_profiles.py` with cross-service token synchronization, dynamically fetching the tokens manifest from Django and injecting `DJANGO_API_TOKEN` and `DJANGO_API_URL` into `/root/.hermes/profiles/<name>/.env`. Added `--push` flag to `cost_monitor` skill to upload spend reports using DRF TokenAuth (Commit: `8a155ee`).
- *2026-09-09*: Empirically verified with 9/9 passing automated unit tests covering positive and negative authorization boundaries, verified live spend report push from inside Hermes container resulting in HTTP 201 (`created_by: bot_cost_controller`), and verified blocking of unauthorized task creation attempts from `bot_cost_controller` (HTTP 403 Forbidden).
- *2026-09-09*: Synchronized system documentation in `docs/ai_wiki/index.md` and `docs/ai_wiki/architecture.md`.

### 4. Current Focus
Phase 3 completed and merged into main (Commit: `a2a6509`).

---

## Phase 4: Unified Django User-Profile Architecture & Live Hermes Profile Selector (COMPLETED)

### 1. Objective & Scope
Refactor the system template from an isolated, hardcoded `AgentProfile` table into an idiomatic, standard Django `UserProfile` architecture.
- Every user is an `auth.User` with an automatically created 1-to-1 `Profile` via Django `post_save` signals.
- Users are categorized with `is_agent` flag and `user_type` choice (`human`, `agent`, `client`).
- Integrate a live Hermes profile discovery service and endpoint (`GET /api/hermes/profiles/`).
- Enhance Django Admin with `ProfileInline` on `UserAdmin` featuring an interactive dropdown of Hermes profiles with an asynchronous 🔄 **Reload Profiles** button.
- Maintain seamless integration with RBAC groups, service accounts, and Hermes profile runtime.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Docker Volume Mount & Live Hermes Discovery Service (`/api/hermes/profiles/`)** - COMPLETED (Commit: `40b4973`)
- [x] **Sub-task 2: Unified Profile Model & Lifecycle Signal (`User` -> `Profile` 1-to-1)** - COMPLETED (Commit: `0b48728`)
- [x] **Sub-task 3: Single-Screen Django Admin UI & Live Hermes Reload Widget** - COMPLETED (Commit: `cfaf404`)
- [x] **Sub-task 4: Update ViewSets, Serializers & Seeding Logic (`seed_profiles.py`)** - COMPLETED (Commit: `1057408`)
- [x] **Sub-task 5: Empirical Testing & Verification** - COMPLETED (11/11 passing tests & browser verification)
- [x] **Sub-task 6: Documentation Synchronization (Wiki & Architecture)** - COMPLETED (Commit: `1b4c88c`)

### 3. Key Decisions & Deviations (Phase 4)
- *2026-09-09*: Initialized Phase 4 on branch `feat/unified-user-profile-architecture` per user's architectural direction to standardize user profiles and implement a live Hermes profiles selector.
- *2026-09-09*: Mounted `../agent_service/profiles` read-only into `/app/agent_profiles/` in `backend/docker-compose.yml` to give Django real-time visibility into engine profiles without external network dependencies.
- *2026-09-09*: Built `HermesDiscoveryService` and `GET /api/hermes/profiles/` returning live profile metadata (name, display name, role, default model) directly from the engine (Commit: `40b4973`).
- *2026-09-09*: Evolved `AgentProfile` to unified `Profile` linked 1-to-1 to `auth.User`, added `is_agent`, `user_type`, and `hermes_profile_name`. Created `signals.py` with `post_save` receiver on `User` to automatically provision profiles. Applied zero-data-loss migrations `0005_unified_user_profile` and `0006_alter_profile_display_name_alter_profile_role` (Commit: `0b48728`).
- *2026-09-09*: Enhanced Django Admin with single-screen `CustomUserAdmin` embedding `ProfileInline`, visual user classification badges (`🤖 Agent`, `👤 Staff`, `🌐 Client`), and an asynchronous **🔄 Reload Profiles** button powered by `hermes_profile_selector.js` that dynamically populates the `<select>` dropdown and auto-fills role and display name (Commit: `cfaf404`).
- *2026-09-09*: Updated `ProfileViewSet`, `ProfileSerializer`, and `seed_profiles.py` to target `Profile`, passing 11/11 automated unit tests and visual browser subagent verification (Commit: `1057408`).
- *2026-09-09*: Synchronized system documentation across `docs/ai_wiki/index.md` and `docs/ai_wiki/architecture.md`.
- *2026-09-09*: Merged `feat/unified-user-profile-architecture` into `main` branch. All features verified and synchronized.

### 4. Current Focus
Phase 4 completed and merged into main (Commit: `6e688bc`). Transitioning to Phase 5.

---

## Phase 5: Centralized Automation Engine, Service Registry & Celery Infrastructure (COMPLETED)

### 1. Objective & Scope
Build a centralized, domain-agnostic Automation and Event-Driven Orchestration Engine in Django (`backend/apps/automation/`) powered by Celery and Celery Beat:
- Support Model Event Triggers (CRUD events across any current or future Django app models).
- Support Time-Based Triggers (`once` and `recurring` across seconds, minutes, hours, days, weeks, months) managed by `django-celery-beat`.
- Implement a 4-category Service Registry (`hermes_agent`, `internal_app`, `script_service`, `external_webhook`) with zero-touch discovery.
- Implement the Flagship Auto-Provisioning Action for Hermes Agent Profiles (creating bot users, generating DRF tokens, and writing runtime `.env` files directly into Hermes).
- Provide a rich Django Admin dashboard with active/pause toggles and execution audit logs (`AutomationLog`).

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Celery & Celery Beat Scaffolding & Docker Compose Configuration** - COMPLETED (Commit: `443576f`)
- [x] **Sub-task 2: Dynamic Service Registry & Core Automation Engine (`apps.automation`)** - COMPLETED (Commit: `196c3cd`)
- [x] **Sub-task 3: Celery Tasks & Celery Beat Schedule Integration** - COMPLETED (Commit: `e351a8c`)
- [x] **Sub-task 4: Rich Administrative Interface & Dynamic Model/App Dropdowns** - COMPLETED (Commit: `8ebdfd1`)
- [x] **Sub-task 5: Flagship Use Case & Seeding: Dynamic Hermes Profile Auto-Provisioner** - COMPLETED (Commit: `58a9ac6`)
- [x] **Sub-task 6: Comprehensive Automated Testing & Empirical Verification** - COMPLETED (Commit: `89066bd`)
- [x] **Sub-task 7: LLM Wiki & Architecture Documentation Synchronization** - COMPLETED (Commit: `a70d8d0`)

### 3. Key Decisions & Deviations (Phase 5)
- *2026-09-09*: Initialized Phase 5 on branch `feat/centralized-automation-engine`.
- *2026-09-09*: Selected Celery + Celery Beat + Redis backed by `django-celery-beat` database scheduler per user request for unified, heavy-workload task execution.
- *2026-09-09*: Configured profile volume mounts to read-write (`rw`) across `backend/docker-compose.yml` to allow Django automation workers to provision agent profiles and `.env` credentials dynamically into `/app/agent_profiles/` and `/app/hermes_runtime_profiles/`.
- *2026-09-09*: Implemented `make_json_serializable()` in `engine.py` to prevent PostgreSQL JSONField serialization crashes when handling UUID primary keys (`Profile.id`) and `datetime` objects.
- *2026-09-09*: Decoupled model signal bootstrapping in `AppConfig.ready()`: core models (`User`, `Profile`, `AgentTask`) are hooked in memory, while custom rule models are registered safely via `post_migrate` and `AutomationRule.save()`, completely eliminating startup `RuntimeWarning: Accessing the database during app initialization is discouraged`.
- *2026-09-09*: Empirically validated dynamic Hermes profile provisioning: creating an agent user triggered the Celery worker, generated DRF Token, created declarative files in `/app/agent_profiles/`, and injected `.env` into `/app/hermes_runtime_profiles/`, recognized immediately by Hermes Agent runtime.
- *2026-09-09*: Added 11 automated unit tests in `apps/automation/tests.py` covering registry, condition matching, once/recurring schedules, Celery task execution, Beat synchronization, live provisioning action, and REST API. Full test suite passing at 22/22 (100%).

### 4. Current Focus
Phase 5 completed. Moving to Phase 5.1 (Admin UX Cleanliness & Odoo-Style State Transition Engine).

---

## Phase 5.1: Admin UX Cleanliness & Odoo-Style State Transition Engine (COMPLETED)

### 1. Objective & Scope
Refine the Automation Engine per user feedback and Odoo's design principles:
- **Admin Sidebar Polish**: Unregister raw Celery Beat plumbing models (`ClockedSchedule`, `CrontabSchedule`, `IntervalSchedule`, `SolarSchedule`, `PeriodicTask`) from Django Admin to eliminate confusing tables.
- **Naming Alignment**: Rename `AutomationRule` verbose names to "Automation Action" / "Automation Actions".
- **Odoo-Style State Transitions**: Support field-level change triggers (`trigger_field`) with `previous_value` and `target_value` state transition conditions.
- **Empirical Validation**: Automated test coverage and admin unregistration verification.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Admin Cleanup & Verbose Naming Alignment** - COMPLETED (Commit: `584141c`)
- [x] **Sub-task 2: State Transition & Field Change Detection Engine** - COMPLETED (Commit: `584141c`)
- [x] **Sub-task 3: Forms & Admin UI Integration** - COMPLETED (Commit: `584141c`)
- [x] **Sub-task 4: Automated Testing & Verification** - COMPLETED (Commit: `584141c`)
- [x] **Sub-task 5: Documentation & Architecture Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 5.1)
- *2026-09-09*: Initiated Phase 5.1 per user audio feedback regarding confusing Celery Beat table names (`Clocked`, `Crontabs`, `Solar events`, `Periodic tasks`) and preference for "Automation Actions" and Odoo-style state transition triggers.
- *2026-09-09*: Unregistered `ClockedSchedule`, `CrontabSchedule`, `IntervalSchedule`, `SolarSchedule`, and `PeriodicTask` from `admin.site` in `backend/apps/automation/admin.py`, keeping the sidebar clean and dedicated exclusively to high-level **Automation Actions** and **Automation Logs**.
- *2026-09-09*: Added `trigger_field`, `previous_value`, and `target_value` to `AutomationRule` with migration `0002_alter_automationrule_options_and_more`.
- *2026-09-09*: Implemented lightweight `pre_save` signal hook caching `_automation_old_values` on model instances so `AutomationEngine` accurately detects changed fields and validates `previous_value` and `target_value` transitions without unnecessary database overhead.
- *2026-09-09*: Added unit tests verifying Celery Beat models are unregistered from Admin, and verified positive/negative test cases for state transitions. Full test suite passing at 24/24 (100%).

### 4. Current Focus
Phase 5.1 completed. Ready for user review and merge into `main`.




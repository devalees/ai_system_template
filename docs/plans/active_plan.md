# Implementation Plan: Universal AI System Template & Agent Ecosystem

- **Status**: IN_PROGRESS <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `feat/security-guard-core-profile`
- **Last Updated**: 2026-09-11 13:05:00+03:00

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
Phase 5.1 completed. Transitioning to Phase 6 (Next-Gen Odoo-Style Automation Actions).

---

## Phase 6: Next-Gen Odoo-Style Automation Actions (COMPLETED)

### 1. Objective & Scope
Elevate `apps.automation` to a fully dynamic, declarative, and observable workflow platform inspired by Odoo:
- **Semantic Separation**: Rename `target_model` to `trigger_model` (source) and introduce a true `target_model` (destination).
- **Target Model CRUD Operations**: Enable direct record `create`, `update`, and `delete` on destination models.
- **Dynamic Field Mapping**: Map triggered record attributes and static defaults into target model fields, respecting required schema constraints.
- **Signal Reification & System Protection**: Register all core routines (Hermes provisioning, spend alerts, QA review routing) as non-deletable `is_system=True` records.
- **Reactive Dynamic Admin UI**: Conditional section toggling, dynamic AJAX field loading, visual condition builder, and required-field mapping table.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Data Model Evolution & Database Migration (`apps.automation.models.py`)** - COMPLETED (Commit: `5128051`)
- [x] **Sub-task 2: Dynamic Model & Field Introspection API (`apps.automation.views.py`)** - COMPLETED (Commit: `4d61b19`)
- [x] **Sub-task 3: Execution Engine & Target Model CRUD Handler (`apps.automation.engine.py`)** - COMPLETED (Commit: `f4e49aa`)
- [x] **Sub-task 4: System Signal Reification & Seed Data (`seed_automations.py`)** - COMPLETED (Commit: `9ba20dd`)
- [x] **Sub-task 5: Reactive Dynamic Admin UI (`automation_reactive_admin.js` & `admin.py`)** - COMPLETED (Commit: `9267e59`)
- [x] **Sub-task 6: Automated Testing & Empirical Verification** - COMPLETED (Commit: `32233c8`)
- [x] **Sub-task 7: Documentation & Architecture Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 6)
- *2026-09-09*: Planned Phase 6 based on user feedback to bring true Odoo-style target model record operations, field mapping, system signal reification, and reactive UI into the engine.
- *2026-09-09*: Successfully migrated `apps.automation.models.py` (migration `0003`), renaming `target_model` to `trigger_model` and adding `target_model`, `target_operation`, `field_mappings`, `condition_rules`, and `is_system` protection.
- *2026-09-09*: Implemented dynamic Model & Field Introspection API (`GET /api/automation/introspection/?model=...`), returning real-time schema specifications, field types, requirement constraints, and choices.
- *2026-09-09*: Upgraded `AutomationEngine` with visual `condition_rules` evaluator (supporting numeric, string, list, and null operators) and direct target model CRUD handlers (`create`, `update`, `delete`) with template expression interpolation (`{{var}}`).
- *2026-09-09*: Reified core system workflows (`Auto-Provision Hermes Profile`, `Daily Spend & Token Audit`, `QA Review Routing`, `Daily Budget Alert`) with `is_system=True` in `seed_automations.py`, and implemented deletion locks across `models.py` and `admin.py`.
- *2026-09-09*: Implemented reactive dynamic Django Admin UI in `automation_reactive_admin.js` featuring dynamic conditional fieldset toggles, live AJAX schema introspection, interactive field mapping pills, and quick rule builders.
- *2026-09-09*: Added comprehensive automated unit test suite in `apps/automation/tests.py` verifying introspection API, CRUD operations, condition rules, system protection, and seed data. 100% test pass rate across 33 test cases.

### 4. Current Focus
Phase 6 completed. Transitioning to Phase 7 (Decoupled Triggers & Universal System Signal Reification).

---

## Phase 7: Decoupled Triggers & Universal System Signal Reification (COMPLETED)

### 1. Objective & Scope
Evolve the automation platform to a 1-to-N workflow pipeline architecture inspired by modern event-driven engines (Zapier, GitHub Actions, Odoo):
- **Decoupled 1-to-N Models**: Split `AutomationRule` into `AutomationTrigger` ("WHEN & UNDER WHAT CONDITIONS") and `AutomationAction` ("WHAT TO DO"), supporting multiple sequenced actions (`sequence=10, 20...`) per trigger.
- **Unified Asynchronous Celery Execution**: All actions execute through Celery distributed workers, ensuring uniform background processing, Redis queueing, non-blocking HTTP requests, and standardized execution logs (`AutomationLog`).
- **Universal System Signal Reification**: Reify core Django lifecycle routines (including `auth.User` ➔ `integration.Profile` creation) into system automation triggers and actions, guaranteeing 100% centralized observability in `AutomationLog`.
- **Reactive Multi-Action Admin UI**: `AutomationTriggerAdmin` embedding `AutomationActionInline` to configure triggers and visual action pipelines on a unified screen.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Data Model Decomposition & Migration (`AutomationTrigger` & `AutomationAction`)** - COMPLETED (Commit: `de2391b`)
- [x] **Sub-task 2: Execution Engine Pipeline & Unified Celery Task Dispatch** - COMPLETED (Commit: `b2daa35`)
- [x] **Sub-task 3: Celery Beat Scheduler Refactoring & Trigger Synchronization** - COMPLETED (Commit: `b2daa35`)
- [x] **Sub-task 4: System Signal Reification & Seed Data (`User` ➔ `Profile` & Core Workflows)** - COMPLETED (Commit: `9b43f21`)
- [x] **Sub-task 5: Reactive Multi-Action Admin UI (`AutomationActionInline` & `admin.py`)** - COMPLETED (Commit: `9b43f21`)
- [x] **Sub-task 6: Automated Testing & Empirical Verification (35 Tests Passing)** - COMPLETED (Commit: `1f659ed`)
- [x] **Sub-task 7: Documentation & Architecture Synchronization** - COMPLETED (Commit: `docs`)

### 3. Key Decisions & Deviations (Phase 7)
- *2026-09-09*: Initiated Phase 7 per user design feedback to decouple triggers from actions, enabling 1-to-N reusable execution pipelines and centralizing all system signals into the audit log.
- *2026-09-09*: Selected unified Asynchronous Celery execution for all automated actions per user directive, eliminating `sync` mode complexity and standardizing all background processing and logs through Celery distributed workers.
- *2026-09-09*: Successfully decomposed `AutomationRule` into `AutomationTrigger` and `AutomationAction` (migration `0004_decouple_triggers_and_actions.py`), seamlessly migrating all existing rules and logs without data loss.
- *2026-09-09*: Upgraded `AutomationEngine` to dispatch 1-to-N actions sequentially via Celery task `execute_automation_action_task.delay(action.id, context, trigger_source)`, writing distinct `AutomationLog` entries linked to both trigger and action.
- *2026-09-09*: Reified `auth.User` creation into default system automation workflow (`Auto-Provision Profile on User Creation` trigger ➔ `Provision Django User Profile` action handler).
- *2026-09-09*: Updated `automation_reactive_admin.js` to support multi-action inline rows with dynamic AJAX schema introspection pills and visual condition presets.
- *2026-09-09*: Verified 100% test pass rate across 35 unit test cases (core registry, 1-to-N pipelines, target CRUD, introspection, celery tasks, and signals).

### 4. Current Focus
Phase 7 completed. Moving into Phase 8.

---

## Phase 8: Interactive Condition Rules Table Builder & Date Formatting Engine (COMPLETED)

### 1. Objective & Scope
Transform the condition rules interface in Django Admin from a raw JSON textarea into a modern, interactive, spreadsheet-like Table Builder (parity with Odoo Domain Builder / Zapier Filters):
- **Interactive Table Component**: Editable columns for Field, Operator, Expected Value, and Action (Delete).
- **Intelligent Field Discovery**: Dynamically populated dropdown matching fields of the selected `trigger_model`.
- **Date & Temporal Value Helpers**: Explicit helper text and format badges instructing the user on Django/database date syntax: `YYYY-MM-DD` (e.g. `2026-09-09`), with dynamic input placeholders and date pickers.
- **Engine Date Comparison Capabilities**: Upgrade `AutomationEngine.evaluate_single_condition` to support accurate `<, <=, >, >=` chronological comparisons on dates and datetimes.
- **Two-Way State Synchronization**: Continuous synchronization between the visual table and the underlying `JSONField` form field.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Engine Temporal & Date Comparison Upgrade (`apps.automation.engine.py`)** - COMPLETED
- [x] **Sub-task 2: Interactive Condition Rules Table Component (`automation_reactive_admin.js`)** - COMPLETED
- [x] **Sub-task 3: Date & Syntax Guidance Card in Admin UI** - COMPLETED
- [x] **Sub-task 4: Automated Testing & Verification for Date Comparisons (36 Tests Passing)** - COMPLETED
- [x] **Sub-task 5: Documentation & Architecture Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 8)
- *2026-09-09*: Initiated Phase 8 per user directive to replace raw JSON condition editing with a visual table and provide explicit Django database date formatting guidance (`YYYY-MM-DD`).
- *2026-09-09*: Enhanced `AutomationEngine.evaluate_single_condition` with `try_parse_temporal` to parse pure `YYYY-MM-DD` date strings and ISO datetimes, enabling chronological comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`) without numeric conversion failures.
- *2026-09-09*: Implemented `auto-rules-container` with dynamically generated rows, type badges, operator selectors, and two-way JSON serialization in `automation_reactive_admin.js`.
- *2026-09-09*: Added inline date helper card explicitly documenting the Django ISO date standard `YYYY-MM-DD` (e.g. `2026-09-09`), timestamps (`YYYY-MM-DD HH:MM:SS`), numbers, and boolean formats.
- *2026-09-09*: Verified 100% test pass rate across 36 unit test cases (including temporal date comparison tests).

### 4. Current Focus
Phase 8 completed. Transitioning to Phase 9.

---

## Phase 9: Unified Filter Conditions Engine with Boolean Logic (AND/OR) & Visual Group Builder (COMPLETED)

### 1. Objective & Scope
Unify `filter_conditions` and `condition_rules` into a single, comprehensive Filter Conditions engine supporting full Boolean algebra (`AND`, `OR`, and nested `(...)` condition groups):
- **Unified Boolean Tree Data Structure**: Tree representation supporting combinators (`AND`, `OR`), leaf rules (`field`, `operator`, `value`), and recursive sub-groups (`(A OR B) AND (C OR D)`).
- **Recursive Engine Evaluation**: Upgrade `AutomationEngine.evaluate_filter_tree` to recursively resolve leaf rules and combinator groups with short-circuiting and date/temporal comparison support.
- **Visual Group Builder Component (Option A)**: In `automation_reactive_admin.js`, render indented condition group cards with combinator toggles (`Match ALL (AND)` / `Match ANY (OR)`), `+ Add Condition`, `+ Add Group (...)`, delete buttons, and dynamic field/date helpers.
- **Full Backward Compatibility**: Seamlessly evaluate legacy flat dicts (`{"is_agent": true}`) and flat lists while synchronizing state into the unified filter field.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Recursive Boolean Engine & Unified Filter Evaluation (`apps.automation.engine.py`)** - COMPLETED (Commit: `92170d4`)
- [x] **Sub-task 2: Visual Group Builder Component with Indented Cards (`automation_reactive_admin.js`)** - COMPLETED (Commit: `92170d4`)
- [x] **Sub-task 3: Form & Admin Unification (`forms.py` & `admin.py`)** - COMPLETED (Commit: `92170d4`)
- [x] **Sub-task 4: Automated Testing for Complex Boolean Trees & Groups (42 Tests Passing)** - COMPLETED (Commit: `92170d4`)
- [x] **Sub-task 5: Documentation & Architecture Synchronization** - COMPLETED (Commit: `92170d4`)

### 3. Key Decisions & Deviations (Phase 9)
- *2026-09-09*: Selected Option A (Visual Group Blocks with Indentation) per user preference, eliminating unmatched parentheses syntax errors.
- *2026-09-09*: Unified `filter_conditions` and `condition_rules` into a single authoritative filter system with transparent legacy compatibility and two-way JSON synchronization.
- *2026-09-09*: Verified lifecycle behavior: for database model events (`created`, `updated`, `deleted`), filters run in-memory against in-flight snapshot context, while for time-based triggers they act as query parameters.
- *2026-09-09*: Expanded test suite with comprehensive tests verifying root AND/OR combinators, nested groups, multi-level nesting, temporal date comparison inside boolean groups, and in-flight model event dispatch.

### 4. Current Focus
Phase 9 complete. Transitioning to Phase 10.

---

## Phase 10: Action Params Assistant, Persona-Specific Prompt Presets & Template Resolution (COMPLETED)

### 1. Objective & Scope
Address the UI and runtime gap for Action Parameters (`action_params`) across Hermes Agent Profiles and registered actions:
- **Action Params Assistant Panel (`automation_reactive_admin.js`)**:
  - Dynamically render an interactive guide panel above `action_params` in both `AutomationActionAdmin` and inline action rows.
  - Automatically detect the selected `action_type` (e.g. `hermes_profile:cost_controller`, `qa_auditor`, `orchestrator`, `generic_webhook`).
- **Persona-Specific Prompt Presets**:
  - Provide 1-click preset buttons that immediately populate production-ready JSON into `action_params` (e.g. Daily Spend Audit, Task Spend Verification, QA Output Review, Triage & Task Decomposition).
- **Clickable Context Variable Insertion**:
  - Display available trigger context variables (`{{pk}}`, `{{task_name}}`, `{{cost_usd}}`, `{{username}}`, `{{status}}`, `{{now}}`) that insert into `action_params` at the current cursor position.
- **Dynamic Template Resolution in Engine (`apps.automation.engine.py`)**:
  - Upgrade `AutomationEngine.execute_action` to resolve template variables (`{{...}}`) inside `action_params` values against the trigger context before execution.
- **Comprehensive Unit Testing**:
  - Verify parameter interpolation, Hermes dispatch with resolved prompt strings, and UI regression coverage.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Dynamic Template Resolution for `action_params` in `AutomationEngine` (`engine.py`)** - COMPLETED (Commit: `adeddac`)
- [x] **Sub-task 2: Persona-Specific Prompt Presets & Preset Registry (`registry.py` / `actions.py`)** - COMPLETED (Commit: `adeddac`)
- [x] **Sub-task 3: Action Params Assistant Component in Reactive Admin UI (`automation_reactive_admin.js`)** - COMPLETED (Commit: `adeddac`)
- [x] **Sub-task 4: Automated Testing for Interpolated Action Params (44 Tests Passing)** - COMPLETED (Commit: `adeddac`)
- [x] **Sub-task 5: Documentation, Architecture Synchronization & Verification** - COMPLETED (Commit: `adeddac`)

### 3. Key Decisions & Deviations (Phase 10)
- *2026-09-09*: Added prompt presets tailored to the 5 standard Hermes Agent personas (`cost_controller`, `qa_auditor`, `orchestrator`, `comms_agent`, `archivist`).
- *2026-09-09*: Implemented recursive template interpolation across `action_params` dictionaries and lists so any parameter value can dynamically reference trigger context variables.
- *2026-09-09*: Added `Media` class to `AutomationActionAdmin` so both standalone Action views and inline action rows render the assistant.
- *2026-09-09*: Verified 44/44 unit tests passing across all Django applications.

### 4. Current Focus
Phase 10 complete. Transitioned to Phase 11.

---

## Phase 11: Direct On-Page Automation Execution & Context Builder (COMPLETED)

### 1. Objective & Scope
Provide direct 1-step test execution mechanisms (`▶ Run Pipeline Now` and `▶ Run Action Now`) on both `AutomationTrigger` and `AutomationAction` Django admin change forms and list views, eliminating the need to leave the page or fabricate dummy records in other tables to test actions:
- **Direct On-Page Execution Buttons**:
  - Top `object-tools` button on `AutomationTrigger` change form: `▶ Run Pipeline Now`.
  - Top `object-tools` button on `AutomationAction` change form: `▶ Run Action Now`.
  - Injected button in `.submit-row` next to the `Save` button at the bottom of both change forms.
  - Inline row button on `AutomationActionInline`: `▶ Run Step #{sequence}: {name}`.
  - Action column `Execute` in both changelists (`▶ Run Pipeline` and `▶ Run Action`).
- **Rich Execution Context Builder**:
  - Automatically queries the monitored `trigger_model` or `target_model` for its latest live record or synthesizes sensible default test values (`task_name`, `cost_usd`, `status`, `username`, etc.).
  - Ensures prompt template variables (`{{task_name}}`, `{{cost_usd}}`, `{{username}}`) evaluate cleanly without missing keys.
- **Engine Manual / Force Execution Support**:
  - Updated `AutomationEngine.execute_trigger` and `AutomationEngine.execute_action` to allow manual testing (`force_execution: True`) without skipping due to inactive status or condition rules mismatch during debugging.
- **Unified Asynchronous Dispatch**:
  - Dispatches tasks to the Celery worker queue immediately, displaying the Celery Task ID in admin success notifications and logging full audit entries in `AutomationLog`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Change Form Templates with Object-Tools Actions (`templates/admin/automation/...`)** - COMPLETED (Commit: `15bd454`)
- [x] **Sub-task 2: Rich Execution Context Builder & Admin URL Endpoints (`apps.automation.admin.py`)** - COMPLETED (Commit: `15bd454`)
- [x] **Sub-task 3: Reactive Submit-Row & Inline Button Injection (`automation_reactive_admin.js`)** - COMPLETED (Commit: `15bd454`)
- [x] **Sub-task 4: Engine Force-Execution & Inactive Bypass (`apps.automation.engine.py`)** - COMPLETED (Commit: `15bd454`)
- [x] **Sub-task 5: Automated Testing & Verification (49 Tests Passing)** - COMPLETED (Commit: `15bd454`)
- [x] **Sub-task 6: Documentation & Architecture Synchronization** - COMPLETED (Commit: `15bd454`)

### 3. Key Decisions & Deviations (Phase 11)
- *2026-09-09*: Implemented `build_execution_context` in `admin.py` to automatically bridge the gap between trigger models and action prompts, pulling live records or falling back to clean defaults so operators never need to leave the page or create dummy records in other apps.
- *2026-09-09*: Added `force_execution` flag to allow on-demand testing of draft or paused triggers/actions from the admin UI.
- *2026-09-09*: Implemented custom change form templates (`change_form.html`) and reactive `.submit-row` injection so the execute button is readily accessible both at the top and bottom of the page.
- *2026-09-09*: Added `AutomationDirectExecutionTests` in `tests.py` covering context extraction, fallback defaults, redirect endpoints, and HTML button formatters. Test suite expanded to 49/49 passing unit tests.
- *2026-09-09*: Resolved Hermes Agent Gateway authentication issue (HTTP 401 in AutomationLog #7). Synchronized `API_SERVER_KEY` and `HERMES_API_KEY` across backend environment and settings, updated `actions.py` and `engine.py` to flag HTTP 4xx/5xx responses as 'failed', and verified successful end-to-end execution in AutomationLog #9 (12.8s runtime, full multi-profile token & budget audit generated).
- *2026-09-09*: Resolved HTTP read timeout issue (Read timed out at 30s in AutomationLog #10). Introduced configurable `HERMES_REQUEST_TIMEOUT` (default: 120s with 10s connect timeout) in `settings.py` and `actions.py`. Verified end-to-end execution in AutomationLog #11 (24.6s runtime, 85 calls audited, status: success).
- *2026-09-09*: Diagnosed and resolved duplicate action execution and log entries (Logs #13 & #14). Identified that migration `0004` auto-created generic actions (`f"{trigger.name} - Action"`), while `seed_automations.py` created canonical actions with distinct names, resulting in two active actions on Triggers 2, 3, 4, and 5. Re-linked all historical logs to canonical action records, deleted legacy duplicate actions, and added automated reconciliation logic to `seed_automations.py` to prevent future duplicates. All 49 unit tests passing.

### 4. Current Focus
Phase 11 complete, authenticated end-to-end with Hermes Agent runtime, duplicate actions reconciled, and empirically validated. All 49 unit tests passing.

---

## Phase 12: Core Foundations, Modular App Settings & Multi-Language Engine (`apps.core`) (COMPLETED)

### 1. Objective & Scope
Establish foundational abstract models, a centralized Odoo-style modular application settings framework, and complete out-of-the-box bilingual (English / Arabic) multi-language architecture:
- **Abstract Base Models**:
  - `TimeStampedModel`: Standardized `created_at` and `updated_at` timestamps with database indexing.
  - `UUIDModel`: Distributed, non-enumerable `id = UUIDField(primary_key=True, default=uuid.uuid4)` to prevent ID enumeration vulnerabilities.
  - `SoftDeleteModel` (Paranoid Model): `is_deleted` and `deleted_at` fields with custom `SoftDeleteManager` and `.restore()` method to prevent accidental data loss.
  - `AuditableModel`: Automatically captures `created_by` and `updated_by` via lightweight request middleware.
- **Odoo-Style Modular Application Settings Framework**:
  - **App-Scoped Registry Pattern**: Each application declares its own configuration parameters cleanly (`conf.py`) via `@register_settings_group`.
  - **Rich Typed Parameters**: Supports `string`, `int`, `float`, `bool` (toggle switches), `choice` (dropdowns), `secret` (encrypted/masked credentials), `image/file` (branding assets, logos), and `json`.
  - **Dual-Layer Resolution with Redis Caching**: Fast runtime access (`get_setting("app.KEY", default=...)`) checking Redis cache first, falling back to PostgreSQL, then to Django `settings.py` or `.env`.
  - **Instant Cache Invalidation**: Automatic Redis cache invalidation on save ensures zero-downtime updates across all running Django processes and Celery workers.
  - **Unified Settings Hub in Django Admin**: Single-screen configuration dashboard organized by app tabs/sidebar (General, AI Agents & Hermes, Automation, Reports & Branding, Notifications).
- **Bilingual & Multi-Language Architecture (English / Arabic i18n & l10n)**:
  - **Core i18n Setup**: `LocaleMiddleware` in request pipeline, `LANGUAGES = [('en', 'English'), ('ar', 'العربية')]`, and centralized message catalogs (`locale/`).
  - **Full Arabic RTL Support**: Right-to-Left layout, BiDi typography detection, and native Django Admin Arabic translations.
  - **User & Profile Language Scoping**: `preferred_language` on `Profile` with dynamic 1-click language switcher in Django Admin.
  - **Model & Content Translation Foundation**: Translation utilities for dynamic database records (JSONB multilingual values e.g. `{"en": "...", "ar": "..."}`).
  - **DRF Content Negotiation**: Auto-resolves error messages and localized responses via HTTP `Accept-Language` headers.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Abstract Base Models (`apps.core.models`) & Request Context Middleware** - COMPLETED (Commit: `3bb8e7b`)
- [x] **Sub-task 2: Dynamic Settings Registry, Type Validators & Secret Encryption** - COMPLETED (Commit: `79178fa`)
- [x] **Sub-task 3: Database Models (`AppSettingValue`) & Redis Caching Layer** - COMPLETED (Commit: `84f944d`)
- [x] **Sub-task 4: Fast Runtime Resolution Service (`get_setting`, `set_setting`) with Code/Env Fallback** - COMPLETED (Commit: `57440c2`)
- [x] **Sub-task 5: Unified Odoo-Style Admin Settings Hub with Categorized App Sidebar** - COMPLETED (Commit: `5f96a80`)
- [x] **Sub-task 6: Bilingual Multi-Language Engine (i18n/l10n, Arabic RTL, LocaleMiddleware & Profile Language)** - COMPLETED (Commit: `fffb6cf`)
- [x] **Sub-task 7: Migrate Existing Hardcoded Constants (Hermes Timeouts, Budget Caps, Defaults) to Settings Registry** - COMPLETED (Commit: `482e44d`)
- [x] **Sub-task 8: Automated Testing & Verification (69 Tests Passing)** - COMPLETED (Commit: `98fd48f`)
- [x] **Sub-task 9: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `5d5f803`)

### 3. Key Decisions & Deviations (Phase 12)
- *2026-09-09*: Initialized Phase 12 on branch `feat/core-foundations-settings-i18n`.
- *2026-09-09*: Implemented thread-safe `CurrentUserMiddleware` utilizing Python 3.11 `contextvars.ContextVar` to automatically populate `created_by` and `updated_by` on `AuditableModel.save()` without leaking context across concurrent requests.
- *2026-09-09*: Implemented `TimeStampedModel`, `UUIDModel`, and paranoid `SoftDeleteModel` with custom `SoftDeleteQuerySet`, `SoftDeleteManager` (filtering out soft-deleted records by default), and `all_objects` manager. Fixed `_state.adding` detection for default UUID primary keys.
- *2026-09-09*: Built declarative `settings_registry` supporting rich typed parameters (`int`, `float`, `bool`, `choice`, `secret`, `json`) and cryptographic secret encryption (`crypto.py`) with UI masking (`••••`).
- *2026-09-09*: Created `AppSettingValue` model with post-save/post-delete signals invalidating Redis cache keys instantly, providing zero-downtime configuration updates across Django and Celery.
- *2026-09-09*: Created single-screen Odoo-style Settings Hub in Django Admin (`/admin/core/appsettingvalue/hub/`) with categorized app sidebar and responsive toggle controls.
- *2026-09-09*: Integrated full bilingual English / Arabic support (`LANGUAGES`, `LocaleMiddleware`, compiled `django.mo` catalogs, and native Arabic RTL BiDi layouts). Added `preferred_language` to `Profile`.
- *2026-09-09*: Migrated hardcoded constants (`HERMES_REQUEST_TIMEOUT`, inference defaults, budget caps) into `apps.automation.conf` and `apps.integration.conf` with runtime fallback.
- *2026-09-09*: Full test suite passing at 69/69 (100% OK) across all test suites.



---

## Phase 13: Metadata Engine, Dynamic Schema & Modular App Runtime (`apps.meta_engine`) (COMPLETED)

### 1. Objective & Scope
Transform the platform into a high-performance **Metadata-Driven Architecture & Declarative Framework** (similar to Odoo `ir.model` and Frappe `DocType`). Provide an Odoo-style **Modular App System** with an App Registry, topological dependency installation, and safe uninstallation lifecycles:
- **Unified Base Model Retrofit**:
  - Unify `AuditableModel` to inherit `TimeStampedModel` in `apps.core.models`, bringing all 4 fields (`created_at`, `updated_at`, `created_by`, `updated_by`) to all existing and future models.
  - Retrofit existing models in `apps.core`, `apps.automation`, and `apps.integration` to inherit `AuditableModel` with automatic actor resolution via `CurrentUserMiddleware`.
- **System Metadata Catalog (`apps.meta_engine.models`)**:
  - `MetaModel`: Dynamic entity definitions (`name`, `label`, `app_label`, `table_name`, `is_system`, `is_auditable`, `is_soft_delete`).
  - `MetaField`: Dynamic field definitions (`model`, `name`, `field_type`, `label`, `required`, `unique`, `default`, `choices`, `fk_target`, `help_text`, `index`).
  - `MetaView`: Declarative layout specifications (form, list/table, kanban, pivot, tree) stored as structured JSON schema trees.
  - `MetaMenu`: Hierarchical navigation items with icons, sequences, parent-child trees, and action triggers.
  - `MetaAction`: Declarative actions (window view actions, server actions, automation triggers).
  - `MetaRule`: Row-level domain filters and field-level permissions.
  - `MetaReport`: Declarative printable reports (`name`, `slug`, `model`, `report_type`: `pdf` | `html`, `template_dsl` / `layout_schema`, `paper_format`, `orientation`, `is_default`).
- **Dynamic PostgreSQL Schema Synchronization (`DynamicSchemaEngine`)**:
  - In-database DDL synchronization using Django's `SchemaEditor`: creates physical PostgreSQL tables, adds/alters columns, creates indexes, and links foreign keys dynamically without requiring manual migration files or server reboots.
  - Python Dynamic Model Factory: compiles `MetaModel` into live in-memory Django models using `type(name, (AuditableModel,), attrs)` registered into `django.apps.apps`.
- **Modular App System & Lifecycle (`AppRegistry`)**:
  - `SystemModule` / `AppRegistry`: Manifest reader for declarative app packages (`app_id`, `name`, `version`, `depends`, `models`, `views`, `menus`, `automations`, `reports`).
  - **Install Engine**: Topological dependency graph resolution (auto-installs prerequisites first), two-pass relational linking, and declarative asset registration (menus, views, automations, printable reports).
  - **Uninstall Engine**: Reverse dependency validation guard, data archiving or automated snapshot backup before safe table drop.
- **Universal Declarative REST API Gateway**:
  - Polymorphic CRUD endpoints (`/api/v1/entities/<model_slug>/`) that dynamically validate, serialize, filter, and paginate records using metadata definitions.
- **Admin App Store & Studio UI**:
  - Visual App Store in Django Admin to 1-click install, upgrade, or uninstall modules.
  - Interactive Metadata Inspector & Form Layout visualizer.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Base Model Retrofit (`AuditableModel` with 4 fields across existing models & migrations)** - COMPLETED (Commit: `7201b05`)
- [x] **Sub-task 2: Metadata Catalog Data Models (`MetaModel`, `MetaField`, `MetaView`, `MetaMenu`, `MetaAction`, `MetaRule`, `MetaReport`)** - COMPLETED (Commit: `c15a627`)
- [x] **Sub-task 3: Dynamic PostgreSQL Schema Engine (SchemaEditor DDL, Column Types & Foreign Key Linking)** - COMPLETED (Commit: `81430eb`)
- [x] **Sub-task 4: Dynamic In-Memory Django Model Factory & Runtime App Registry Injection** - COMPLETED (Commit: `97d117d`)
- [x] **Sub-task 5: Modular App Manifest & Registry Engine (`SystemModule`, Dependency Sorter & Declarative Ingestion [Models, Views, Menus, Automations, Reports])** - COMPLETED (Commit: `5c4874e`)
- [x] **Sub-task 6: Safe App Uninstall & Data Policy Engine (Reverse Dependency Check, Snapshot Backup & Safe Purge)** - COMPLETED (Commit: `c88f594`)
- [x] **Sub-task 7: Universal Declarative REST API Gateway (`/api/v1/entities/<slug>/`)** - COMPLETED (Commit: `9ace2c9`)
- [x] **Sub-task 8: Odoo-Style Admin App Store & Metadata Studio Interface** - COMPLETED (Commit: `024563e`)
- [x] **Sub-task 9: Comprehensive Automated Testing & End-to-End Verification** - COMPLETED (Commit: `d7e2ff3`)
- [x] **Sub-task 10: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `76533bd`)


### 3. Key Decisions & Deviations (Phase 13)
- *2026-09-09*: Pivoted platform architecture to a **Metadata-Driven Architecture & Declarative Framework** with an Odoo-style **Modular App Runtime**.
- *2026-09-09*: Unified `AuditableModel` to inherit `TimeStampedModel`, guaranteeing that every dynamic and domain model automatically receives `id` (UUID), `created_at`, `updated_at`, `created_by`, and `updated_by`.
- *2026-09-09*: Implemented `DynamicModelFactory` in `apps.meta_engine.model_factory` allowing dynamic models to be compiled in-memory as full-fledged Django models inheriting `(UUIDModel, SoftDeleteModel, AuditableModel)` and registered into `django.apps.apps`. Integrated lazy loading, soft deletion, and standard ORM CRUD (Commit: `97d117d`).
- *2026-09-09*: Implemented Modular App Registry Engine with `SystemModule`, `AppManifestReader`, DAG `DependencyResolver`, and multi-pass `AppInstaller` handling models, foreign keys, views, menus, automations, and reports. Added reference demo apps `contacts` and `crm` (Commit: `5c4874e`).
- *2026-09-09*: Implemented `AppUninstaller` in `apps.meta_engine.app_uninstaller` featuring reverse dependency validation guard (blocking uninstall of required modules) and 3 pluggable data retention policies: `archive` (soft-deactivation), `snapshot_backup_and_drop` (JSON record export before DDL drop), and `cascade_drop` (immediate purge) (Commit: `c88f594`).
- *2026-09-09*: Implemented Universal Declarative REST API Gateway in `apps.meta_engine.views` exposing polymorphic CRUD operations (`/api/v1/entities/<model_slug>/`), declarative schema introspection (`/schema/`), dynamic serializers via `DynamicEntitySerializerFactory`, and row-level `MetaRule` security filtering (Commit: `9ace2c9`).
- *2026-09-09*: Implemented Odoo-Style Admin App Store (`/admin/meta_engine/systemmodule/app-store/`) with visual module cards, 1-click install/uninstall buttons, data retention policy selectors, disk synchronization, and live PostgreSQL DDL status badges and API gateway links on `MetaModelAdmin` (Commit: `024563e`).

---

## Phase 14: Multi-Tenancy, Organizations & Workspaces (`apps.tenants`) (COMPLETED)

### 1. Objective & Scope
Implement multi-tenant data isolation and workspace management to support B2B SaaS, multi-department enterprise portals, and client workspaces:
- **Tenant Models**:
  - `Organization` / `Workspace`: `name`, `slug`, `is_active`, `tier/plan`, `metadata` (JSON).
  - `OrganizationMembership`: Junction linking `auth.User` to `Organization` with role-based membership (`owner`, `admin`, `member`, `viewer`, `guest`).
  - `OrganizationInvitation`: Tokenized, expiring email invitations.
- **Tenant Isolation Architecture**:
  - `TenantAwareModel` abstract base class with automatic query filtering and active tenant resolution middleware.
  - Integration with existing `Profile.user_type` and RBAC groups.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Organization, Membership & Invitation Data Models** - COMPLETED (Commit: `642561b`)
- [x] **Sub-task 2: ContextVars Tenant Context & Active Workspace Middleware** - COMPLETED (Commit: `18cebdb`)
- [x] **Sub-task 3: TenantAwareModel Abstract Base & Filtered Managers** - COMPLETED (Commit: `d5e8d4a`)
- [x] **Sub-task 4: Multi-Tenant Declarative Engine Integration (`MetaModel`, Dynamic Factory & Schemas)** - COMPLETED (Commit: `240d64a`)
- [x] **Sub-task 5: Organization Admin, Member Management & REST API Endpoints** - COMPLETED (Commit: `86de7af`)
- [x] **Sub-task 6: Comprehensive Automated Testing & End-to-End Verification** - COMPLETED (Commit: `7162d9b`)
- [x] **Sub-task 7: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `76d5e86`)

### 3. Key Decisions & Deviations (Phase 14)
- *2026-09-09*: Selected **Row-Level Shared-Database Multi-Tenancy** over schema-per-tenant or multi-database routing. Row-level partitioning eliminates DDL migration bottlenecks, connection pool starvation, and complex connection routing while ensuring strict query isolation.
- *2026-09-09*: Implemented `Organization`, `OrganizationMembership`, and `OrganizationInvitation` in `apps.tenants.models`. Auto-provisioned a global default workspace (`Default Workspace`, slug: `default`) via data migration `0002_create_default_organization` to guarantee 100% backward compatibility for existing users and bot accounts.
- *2026-09-09*: Implemented thread-safe and async-safe tenant context management in `apps.tenants.context` using Python 3.11's `contextvars`, accompanied by `tenant_context(org)` and `bypass_tenant_isolation()` context managers.
- *2026-09-09*: Implemented `TenantMiddleware` with a 5-tier resolution strategy: HTTP Header (`X-Workspace-Slug`, `X-Organization-ID`), query parameter (`?workspace=`), host subdomain, user default active membership, and global fallback workspace. Added security gate denying non-members with `403 Forbidden`.
- *2026-09-09*: Built `TenantAwareModel(AuditableModel)` and `TenantManager` with built-in `SoftDeleteQuerySet` parity (`alive()`, `dead()`, `restore()`, `hard_delete()`), automatic tenant binding on save, and explicit `all_objects` bypass manager. Made `organization` foreign key nullable with fallback to support global templates and smooth data migrations.
- *2026-09-09*: Integrated multi-tenancy into declarative `apps.meta_engine`: added `is_tenant_aware` to `MetaModel`, updated `DynamicModelFactory` to compile dynamic models inheriting `TenantAwareModel`, updated `DynamicSchemaEngine` to generate `organization_id` foreign key columns, and configured `UniversalEntityViewSet` to auto-scope REST operations to the active tenant.
- *2026-09-09*: Built REST API endpoints (`/api/v1/organizations/` and `/api/v1/invitations/<token>/accept/`) and customized Django Admin with member inlines, active seat counters, and tier badges. Verified 125/125 system tests passing.

---

## Phase 15: Comprehensive Activity Audit Trail (`apps.audit`) (COMPLETED)

### 1. Objective & Scope
Build an enterprise-grade, immutable activity audit trail tracking human, bot service account, and system actions for compliance (SOC2, GDPR, ISO 27001):
- **Universal Audit Log (`ActivityLog`)**:
  - Fields: `actor` (User/Bot), `action` (`login`, `logout`, `create`, `update`, `delete`, `export`, `impersonate`), `content_type` & `object_id` (Generic Foreign Key to any record), `changes` (structured JSON diff of old vs new values), `ip_address`, `user_agent`, and `timestamp`.
- **Automatic Lifecycle Auditing**:
  - Model signal receiver automatically calculating attribute diffs for registered auditable models.
  - Security event logging (login failures, password resets, permission changes).

### 2. Task Checklist & Progress
- [x] **Sub-task 1: ActivityLog Model & Generic Relationship Architecture** - COMPLETED (Commit: `9ed01f7`)
- [x] **Sub-task 2: Request Context & Client IP Middleware** - COMPLETED (Commit: `9b93474`)
- [x] **Sub-task 3: Automated Signal-Based Model Diffing & Security Event Receivers** - COMPLETED (Commit: `763b01a`)
- [x] **Sub-task 4: Declarative Dynamic Model Audit Integration** - COMPLETED (Commit: `4969ede`)
- [x] **Sub-task 5: Read-Only Audit Admin Dashboard with JSON Diff Viewer & REST API** - COMPLETED (Commit: `6b49d7d`)
- [x] **Sub-task 6: Comprehensive Automated Testing & End-to-End Verification** - COMPLETED (Commit: `0ba21bb`)
- [x] **Sub-task 7: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `58524a3`)

---

## Phase 16: Universal Notifications Engine (`apps.notifications`) (COMPLETED)

### 1. Objective & Scope
Centralized notification dispatcher connecting human users, administrative teams, and autonomous AI agents:
- **Notification Infrastructure**:
  - `Notification`: `recipient`, `actor`, `level` (`info`, `success`, `warning`, `error`), `title`, `message`, `action_url`, `read_at`, `extra_data`.
  - `NotificationPreference`: Per-user multi-channel toggles (`in_app`, `email`, `webhook`, `slack`).
- **Real-Time & Background Dispatching**:
  - Redis-backed unread counter caching.
  - Celery tasks for asynchronous email and webhook notification delivery.
  - Integration with `apps.automation` for automated notification triggers.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Notification & NotificationPreference Data Models** - COMPLETED (Commit: `6ecd134`)
- [x] **Sub-task 2: Dispatcher Service Layer & Multi-Channel Adapters** - COMPLETED (Commit: `612df38`)
- [x] **Sub-task 3: Celery Asynchronous Email & Webhook Tasks** - COMPLETED (Commit: `fe775e2`)
- [x] **Sub-task 4: REST API Endpoints (Inbox, Mark-as-Read, Unread Count)** - COMPLETED (Commit: `a4df246`)
- [x] **Sub-task 5: Automated Testing & Verification (163 Tests Passing)** - COMPLETED (Commit: `a4df246`)
- [x] **Sub-task 6: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `eb0963e`)

---

## Phase 17: Universal Document & Media Management (`apps.media`) (COMPLETED)

### 1. Objective & Scope
Unified file, document, and media management handling user uploads, generated agent reports, exports, PDFs, and attachments:
- **Attachment & Document Architecture**:
  - `Document` / `Attachment`: `file`, `filename`, `file_size`, `mime_type`, `uploaded_by`, `organization`, `is_public`, `checksum_sha256` (deduplication and integrity checking).
  - Generic Foreign Key (`content_type`, `object_id`) allowing documents to be attached to any system record (`AgentTask`, `User`, `Organization`, etc.).
- **Storage & Security**:
  - Docker volume local storage with pluggable S3/MinIO cloud storage abstraction.
  - Secure signed download URLs for private documents.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Document Data Model with SHA-256 Checksums & Generic FK** - COMPLETED (Commit: `c4b1a02`)
- [x] **Sub-task 2: Pluggable Storage Backend & Secure File Serving Service** - COMPLETED (Commit: `8da94e2`)
- [x] **Sub-task 3: Generic Attachment Inline for Django Admin** - COMPLETED (Commit: `b38b55a`)
- [x] **Sub-task 4: REST API Endpoints for File Upload & Retrieval** - COMPLETED (Commit: `3c46420`)
- [x] **Sub-task 5: Automated Testing & Verification (175 Tests Passing)** - COMPLETED (Commit: `3c46420`)
- [x] **Sub-task 6: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `d897113`)

---

## Phase 18: Developer API Gateway, Scoped Keys & Inbound Webhooks (`apps.api_gateway`) (COMPLETED)

### 1. Objective & Scope
Expose secure, programmatic API access and inbound webhook ingestion for third-party SaaS interoperability:
- **Developer API Keys (`APIKey`)**:
  - Secure cryptographically hashed keys (e.g. `agy_live_...`) with granular permission scopes (`read`, `write`, `admin`), expiration dates, and IP allowlisting.
  - DRF authentication backend authenticating API keys on API routes.
- **Inbound Webhooks (`InboundWebhook` / `WebhookEvent`)**:
  - Cryptographic HMAC signature verification (Stripe, GitHub, Shopify, Slack, etc.).
  - Raw payload archival and event status tracking.
  - Bridge into `apps.automation` for automated event dispatching.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: APIKey Model, Hashing & DRF Authentication Backend** - COMPLETED (Commit: `fdb1c27`)
- [x] **Sub-task 2: InboundWebhook Model & HMAC Signature Verifier** - COMPLETED (Commit: `fdb1c27`)
- [x] **Sub-task 3: Inbound Webhook Ingestion API & Automation Bridge** - COMPLETED (Commit: `fdb1c27`)
- [x] **Sub-task 4: Django Admin Key Management & Event Inspector** - COMPLETED (Commit: `fdb1c27`)
- [x] **Sub-task 5: Automated Testing & Verification (184 Tests Passing)** - COMPLETED (Commit: `fdb1c27`)
- [x] **Sub-task 6: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `fdb1c27`)

### 3. Key Decisions & Deviations (Phase 18)
- *2026-09-09*: Initialized `apps.api_gateway` on branch `feat/developer-api-gateway`.
- *2026-09-09*: Created `APIKey` model generating 24-byte hex tokens prefixed with `agy_live_`, storing SHA-256 digests in database and returning raw secret key ONCE upon creation. Added granular `scopes` JSON list, IP allowlist, and `expires_at` support.
- *2026-09-09*: Implemented `APIKeyAuthentication` subclassing DRF `BaseAuthentication`, parsing `X-API-Key` or `Authorization: Api-Key <raw_key>` headers, validating prefix, verifying SHA-256 hash digest, checking expiration and IP allowlists, setting active tenant context on request, and updating `last_used_at`. Added `authenticate_header` returning `Api-Key realm="api"` for proper 401 Unauthorized formatting.
- *2026-09-09*: Implemented `InboundWebhook` and `WebhookEvent` models supporting GitHub, Stripe, Slack, and Custom HMAC SHA-256 signature verification in `signature.py`.
- *2026-09-09*: Implemented public ingestion endpoint `POST /api/v1/gateway/webhooks/<slug>/ingest/` (using `InboundWebhook.all_objects` to handle public unauthenticated webhooks) and ViewSets for `APIKey`, `InboundWebhook`, and `WebhookEvent`.
- *2026-09-09*: Registered models in Django Admin with prefix search, read-only hashes, and event payload inspectors.
- *2026-09-09*: Added comprehensive unit tests in `tests.py`. Verified 184/184 tests passing across all 18 applications.

---

## Phase 19: Dynamic Visual Reporting & PDF Generation Engine (`apps.reports`) (COMPLETED)

### 1. Objective & Scope
Implement an enterprise-grade, dynamic reporting engine in Django capable of rendering both interactive HTML views and pixel-perfect vector PDFs:
- **Dual-Representation Storage**:
  - `ReportTemplate`: `name`, `slug`, `target_model` (bound via introspection), `page_format` (`A4`, `Letter`, `thermal_80mm`), `orientation` (`portrait`, `landscape`), `layout_schema` (JSON visual coordinate tree for frontend drag-and-drop builder), `compiled_html` (Jinja2/Django HTML+CSS template with `@page` media rules), `is_default`, `is_active`.
  - `ReportExecutionLog`: Audit log capturing generation duration, requesting actor, output file size, format (HTML/PDF), and status.
- **Rendering & Conversion Pipeline**:
  - CSS Paged Media (`@page { size: A4 portrait; margin: 10mm; }`) with header/footer pagination (`counter(page)`).
  - Python-native WeasyPrint vector PDF rendering backend inside backend container.
  - Multi-language & RTL Arabic typography support (`Cairo`, `Amiri`, UTF-8).
- **Frontend Designer Integration API**:
  - Introspection API bridge exposing dynamic model fields and reverse relationships as draggable tokens.
  - Preview endpoint (`GET /api/v1/reports/templates/<id>/preview/?record_id=...&format=html`) and binary download endpoint (`GET /api/v1/reports/templates/<id>/render/?record_id=...&format=pdf`).
- **Automation & Agent Ecosystem Bridge**:
  - Register `generate_pdf_report` action in `apps.automation` allowing triggers (e.g. Invoice approved, Task completed) to automatically compile reports, attach them to `apps.media`, and dispatch via `apps.notifications`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: ReportTemplate & ReportExecutionLog Data Models (`apps.reports.models`)** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 2: WeasyPrint Engine & CSS Paged Media Service Layer (`apps.reports.engine`)** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 3: Model Introspection Token Bridge & Template Compiler** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 4: REST API Endpoints (Template CRUD, Live HTML Preview, PDF Render)** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 5: Automation Engine Action Registration (`generate_pdf_report`)** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 6: Django Admin Interface with Live Preview Actions** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 7: Automated Testing & Verification (193 Tests Passing)** - COMPLETED (Commit: `f1e76d8`)
- [x] **Sub-task 8: LLM Wiki & Architecture Synchronization** - COMPLETED (Commit: `f1e76d8`)

---

## Phase 20: Decouple & Remove Dynamic Metadata Engine (`apps.meta_engine`) (COMPLETED)

### 1. Objective & Scope
Decouple and remove the dynamic metadata engine (`apps.meta_engine`) and PostgreSQL dynamic DDL schema generator (introduced in Phase 13) to return to standard, static Django ORM models across the codebase:
- Unregister `apps.meta_engine` from `INSTALLED_APPS` and URL routers.
- Remove dynamic model lookups and references in `apps/reports`, `apps/tenants`, and `apps/audit`.
- Retain core abstract base models in `apps/core/models.py` (`TimeStampedModel`, `UUIDModel`, `SoftDeleteModel`, `AuditableModel`).
- Remove `apps/meta_engine` module directory.
- Empirically verify 100% test pass rate across all remaining applications.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Unregister `apps.meta_engine` from Settings & URL Routes** - COMPLETED
- [x] **Sub-task 2: Refactor Cross-App References (`apps.reports.engine`, `apps.tenants.tests`, `apps.audit.tests`)** - COMPLETED
- [x] **Sub-task 3: Remove `apps/meta_engine` Module Directory** - COMPLETED
- [x] **Sub-task 4: Comprehensive Test Suite Verification & Database Sanity Check** - COMPLETED
- [x] **Sub-task 5: Documentation & LLM Wiki Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 20)
- *2026-09-10*: Initiated Phase 20 per user directive to revert Phase 13's dynamic metadata engine (`apps.meta_engine`) and maintain standard, explicit Django ORM models across all features. Verified that Phases 14–19 use native models and remain fully functional.
- *2026-09-10*: Successfully unregistered `apps.meta_engine` from settings and routing, removed dynamic model resolution fallback from `apps/reports/engine.py`, cleaned up tests, deleted `apps/meta_engine` module, and verified 100% pass rate across 164 unit tests.

### 4. Current Focus
Phase 20 completed. Proceeding with Phase 21: Enterprise Hardening of Centralized Automation Engine.

---

## Phase 21: Enterprise Hardening of Centralized Automation Engine (`apps.automation`) (COMPLETED)

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 05:08:00+03:00

### 1. Objective & Scope
Harden the centralized automation engine (`apps.automation`) to resolve production race conditions, enhance pipeline execution capabilities, protect against recursion loops, and support multi-tenant workspace isolation:
- **Transaction Safety**: Guarantee Celery tasks fire only after database transactions commit (`transaction.on_commit`).
- **Sequential Pipeline Chaining**: Coordinate multi-action pipelines sequentially and propagate accumulated context between steps with `stop_on_failure` support.
- **Recursion Guard**: Prevent cascading infinite trigger loops with execution depth tracking (`_automation_depth`) and configurable ceiling (`MAX_AUTOMATION_DEPTH`).
- **Multi-Tenancy Scoping**: Add nullable `organization` FK to `AutomationTrigger`, `AutomationAction`, and `AutomationLog`, executing worker tasks within `tenant_context`.
- **Target Model CRUD Sandboxing**: Blacklist internal sensitive framework models (`auth.Permission`, `authtoken.Token`, etc.) from automated manipulation.
- **Failure Resilience**: Support exponential backoff retries for external HTTP integrations.
- **Admin UI Enhancement**: Expose workspace badges, `stop_on_failure` toggles, and execution depth.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Commit: `2540282`)
- [x] **Sub-task 2: Data Models & Database Migration (`apps.automation.models`)** - COMPLETED (Commit: `73f8b72`)
- [x] **Sub-task 3: Signal Dispatch & Transaction Integrity (`signals.py`)** - COMPLETED (Commit: `6ed979e`)
- [x] **Sub-task 4: Execution Engine Hardening (`engine.py`)** - COMPLETED (Commit: `f35d5db`)
- [x] **Sub-task 5: Asynchronous Celery Tasks & Resilience (`tasks.py`, `actions.py`)** - COMPLETED (Commit: `f35d5db`)
- [x] **Sub-task 6: Django Admin UI Refinement (`admin.py`)** - COMPLETED (Commit: `204b264`)
- [x] **Sub-task 7: Automated Testing & Verification (`tests.py`)** - COMPLETED (Commit: `828ac09`)
- [x] **Sub-task 8: Documentation & LLM Wiki Synchronization** - COMPLETED (Commit: pending)

### 3. Key Decisions & Deviations (Phase 21)
- *2026-09-11*: Initialized Phase 21 on branch `feat/automation-enterprise-hardening`. Designed nullable `organization` relationship allowing system triggers to remain global while granting organizations private automation pipelines.
- *2026-09-11*: In `signals.py`, preserved immediate execution when `CELERY_TASK_ALWAYS_EAGER=True` while enforcing `transaction.on_commit` in production to prevent Celery worker race conditions on uncommitted records without breaking synchronous unit tests.
- *2026-09-11*: Unified multi-action pipelines under `execute_pipeline`, passing `record_id` and step outputs forward across sequential actions with circuit-breaker `stop_on_failure` halting.
- *2026-09-11*: Verified 100% pass rate across 170 unit tests in the entire system test suite.

### 4. Current Focus
Phase 21 completed. Proceeding with Phase 22: Centralized Provider Credentials, Zero-Downtime Synchronization, Token Governance & Multi-Agent Handoff.

---

## Phase 22: Centralized Provider Credentials, Zero-Downtime Synchronization, Token Governance & Multi-Agent Handoff (COMPLETED)

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 06:01:00+03:00


### 1. Objective & Scope
Unify LLM provider credentials, token accounting, and agent runtime orchestration inside Django to achieve high security, zero-downtime key rotation, strict cost control, and structured multi-agent collaboration:
- **Centralized Provider Credentials**: Store encrypted LLM API keys (`OpenRouter`, `Gemini`, `OpenAI`, `Anthropic`, `Groq`, `DeepSeek`) in Django using AES encryption at rest, introducing `ProviderCredential` model and registering typed secrets in `apps.integration.conf`.
- **Zero-Downtime Hermes Key Sync**: Exploit Hermes's native per-turn dynamic secret scoping (`build_profile_secret_scope`) by mounting runtime volumes and syncing decrypted credentials on `post_save` directly into `/root/.hermes/.env`, per-profile `.env`, and `auth.json`.
- **Centralized Budget & Token Accounting**: Implement pre-execution budget ceiling checks (`DAILY_BUDGET_CAP_USD`) and parse HTTP response `usage` blocks directly into `SpendReport` and `AgentTask`.
- **Latency & Reasoning Calibration**: Calibrate persona defaults (`orchestrator` and `communications` to `"none"`, `finance` to `"low"`, `qa_auditor` to `"high"`).
- **Structured Inter-Agent Handoff**: Support deliverable propagation between sequential agent pipeline steps via Django `AgentTask`.
- **Django Admin Enhancements**: Expose `ProviderCredentialAdmin` with masked secret input and add a prominent "⚙️ Open Visual Settings Hub" banner to `AppSettingValueAdmin`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Commit: `b7e8167`)
- [x] **Sub-task 2: Provider Credentials Model & Encrypted Storage (`apps.integration.models`, `conf.py`)** - COMPLETED (Commit: `c7b091f`)
- [x] **Sub-task 3: Volume Mounts & Zero-Downtime Credential Sync Service (`apps.integration.services`)** - COMPLETED (Commit: `1b336db`)
- [x] **Sub-task 4: Pre-Execution Budget Gates & Direct Token Accounting (`apps.automation.actions`)** - COMPLETED (Commit: `b169013`)
- [x] **Sub-task 5: Reasoning Calibration & Structured Multi-Agent Handoff** - COMPLETED (Commit: `699efd9`)
- [x] **Sub-task 6: Django Admin UI Refinements & Settings Hub Banner** - COMPLETED (Commit: `6539001`)
- [x] **Sub-task 7: Automated Testing & Empirical Verification** - COMPLETED (Commit: `702a8ae`)
- [x] **Sub-task 8: Documentation & LLM Wiki Synchronization** - COMPLETED (Commit: `5dc4178`)

### 3. Key Decisions & Deviations (Phase 22)
- *2026-09-11*: Initialized Phase 22 on feature branch `feat/provider-credentials-and-agent-governance`. Designed dual-credential management: typed secrets in `apps.integration.conf` (Settings Hub) for global defaults, and `ProviderCredential` relational model for multi-key pools, custom `base_url` endpoints, and per-profile assignment.
- *2026-09-11*: Implemented `ProviderCredential` with AES encrypted `encrypted_api_key` via `apps.core.crypto` and masked secret property. Added `resolve_provider_and_key()` on `Profile` with hierarchical resolution (Direct -> Default Credential -> Settings Hub -> Fallback).
- *2026-09-11*: Implemented `credential_sync` service with volume mounts (`/app/hermes_runtime_data` and `/app/hermes_root_env`). Connected signals so saving a `ProviderCredential` or updating an API key in Settings Hub automatically updates `/root/.hermes/.env`, per-profile `.env` files, and `config.yaml` with zero service downtime.
- *2026-09-11*: Implemented pre-execution budget ceiling gate in `dispatch_hermes_prompt_action` halting requests before dispatch when `DAILY_BUDGET_CAP_USD` is exceeded. Built post-execution direct spend tracking parsing OpenAI-compatible `usage` blocks atomically into `SpendReport` and updating `AgentTask` token/cost fields.
- *2026-09-11*: Calibrated default agent persona reasoning budgets (`orchestrator` & `comms_agent` = `none`, `cost_controller` & `archivist` = `low`, `qa_auditor` = `high`) eliminating 10–15s latency on operational workflows. Enhanced `execute_pipeline` context chaining with `deliverable` propagation.
- *2026-09-11*: Registered `ProviderCredentialAdmin` with masked password widget and manual runtime sync action. Added custom `change_list.html` to `AppSettingValue` with prominent banner button directing to `/admin/core/appsettingvalue/hub/`.
- *2026-09-11*: Created `tests_credentials.py` testing encryption, default constraints, hierarchical key resolution, runtime file sync, budget gates, direct spend recording, and multi-agent pipeline handoff. Verified 100% test pass rate across all 178 tests.

### 4. Current Focus
Phase 22 completed. Provider credentials centralized with zero-downtime hot-syncing, budget governance, calibrated reasoning, and multi-agent handoffs fully operational. Ready to merge into `main`.

---

## Phase 23: Provider Credentials Consolidation, Model Catalog Sorting & Profile Admin Streamlining

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 06:40:00+03:00

### 1. Objective & Scope
Consolidate LLM credentials into a single source of truth (`ProviderCredential`), eliminate redundant secret key fields from the Settings Hub, sort and group models by provider using `<optgroup>`, and streamline the `Profile` admin interface:
- **Single Source of Truth for Credentials**: Remove duplicate API key secrets from `apps.integration.conf` (Settings Hub), leaving only global governance and default parameters (`DEFAULT_PROVIDER`, `DEFAULT_MODEL`, `DEFAULT_REASONING_EFFORT`, `DAILY_BUDGET_CAP_USD`). Update `Profile.resolve_provider_and_key()` and `collect_active_provider_keys()`.
- **Model Catalog Categorization & Sorting**: Categorize OpenRouter models by vendor prefix (`Google`, `Anthropic`, `OpenAI`, `DeepSeek`, `Meta / LLaMA`, etc.) and sort them alphabetically in `apps.integration.services.hermes_catalog`.
- **Admin Optgroups & Dynamic JS Support**: Structure `ProfileAdminForm` and update `agent_profile_models.js` to render `<optgroup label="...">` elements for clean, categorized model selection.
- **Profile Admin UI Fieldsets**: Organize `ProfileAdmin` fieldsets, moving `provider_credential` into a collapsed "Advanced Credential & Endpoint Overrides" section with descriptive guidance.
- **Automated Verification**: Update test suite to verify consolidation, sorting, optgroups, and run full project tests to ensure 100% pass rate.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Commit: `3291dfa`)
- [x] **Sub-task 2: Credentials Consolidation & Settings Hub De-duplication (`conf.py`, `models.py`, `credential_sync.py`)** - COMPLETED (Commit: `c5bb10f`)
- [x] **Sub-task 3: Model Catalog Vendor Attribution & Alphabetical Sorting (`hermes_catalog.py`)** - COMPLETED (Commit: `60ef1e4`)
- [x] **Sub-task 4: Admin Form Optgroup Grouping & Dynamic JS Support (`forms.py`, `agent_profile_models.js`)** - COMPLETED (Commit: `6166286`)
- [x] **Sub-task 5: Profile Admin Fieldset Streamlining (`admin.py`)** - COMPLETED (Commit: `1b6678f`)
- [x] **Sub-task 6: Automated Testing & Test Suite Verification** - COMPLETED (Commit: `96905cb`)
- [x] **Sub-task 7: Documentation & LLM Wiki Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 23)
- *2026-09-11*: Initiated Phase 23 per user request to eliminate duplicate API key fields in Settings Hub in favor of `ProviderCredential` as the sole source of truth, sort model choices by provider prefix, and clarify the purpose of `provider_credential` on `Profile`.
- *2026-09-11*: Consolidated all credentials into `ProviderCredential`. Removed 6 duplicate secret settings from `apps.integration.conf`. Preserved global governance settings (`DEFAULT_PROVIDER`, `DEFAULT_MODEL`, `DEFAULT_REASONING_EFFORT`, `DAILY_BUDGET_CAP_USD`) in Settings Hub.
- *2026-09-11*: Normalized vendor prefixes in `hermes_catalog.py` (stripping symbols, mapping aliases like `meta`, `gemini`, `zai`, etc.), sorting models alphabetically by vendor group and model name.
- *2026-09-11*: Implemented `<optgroup>` rendering in `ProfileAdminForm` and `agent_profile_models.js`.
- *2026-09-11*: Streamlined `ProfileAdmin` and `ProfileInline` fieldsets, moving `provider_credential` into a collapsed "Advanced Credential & Endpoint Overrides" fieldset with clear guidance.
- *2026-09-11*: Executed complete test suite: 100% pass rate across 181 unit tests.

### 4. Current Focus
Phase 23 completed and verified.

---

## Phase 24: LLM Model Modalities, Visual Capability Badges & Dropdown Indicators

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 07:07:00+03:00


### 1. Objective & Scope
Enrich the model catalog and profile administration UI with comprehensive modality specifications (Text, Vision / Image, Document / File / PDF, Audio / Voice, Video) from OpenRouter and `models.dev`:
- **Catalog Service Modalities Normalization**: Extract `input_modalities` and `output_modalities` across OpenRouter (`architecture.input_modalities`), `models.dev` (`modalities.input`), and Nous Portal in `apps.integration.services.hermes_catalog`. Normalize and expose `format_modality_indicator()` helper.
- **Admin Form Initial Choices**: Enhance `ProfileAdminForm` in `forms.py` to include compact modality indicator emoji badges (e.g. `[🖼️ Vision]`, `[💬 Text]`, `[📁 PDF]`, `[🎙️ Audio]`, `[🎥 Video]`) in `<option>` labels so administrators can identify capabilities at a glance.
- **Dynamic JavaScript & Specifications Card**: Upgrade `agent_profile_models.js` to render a dedicated, stylized **Supported Modalities** section in `#hermes-model-specs-card` with distinct, color-coded badges/chips for input and output capabilities, alongside existing pricing and context window metrics.
- **Automated Testing & Full Verification**: Add comprehensive unit tests verifying modality parsing across OpenRouter, `models.dev`, Nous Portal, and the REST API endpoint `/api/hermes/models/`. Ensure 100% test pass rate across the full 181+ test suite.
- **Documentation Synchronization**: Synchronize `docs/ai_wiki/index.md` and `docs/ai_wiki/architecture.md`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/model-modalities-and-specs-card`, Commit: `30bf0bc`)
- [x] **Sub-task 2: Backend Catalog Modalities Normalization (`hermes_catalog.py`)** - COMPLETED (Commit: `864537b`)
- [x] **Sub-task 3: Django Admin Form Dropdown Modality Indicators (`forms.py`)** - COMPLETED (Commit: `26aa1e0`)
- [x] **Sub-task 4: Dynamic Admin UI & Visual Metrics Card Badges (`agent_profile_models.js`)** - COMPLETED (Commit: `411d77d`)
- [x] **Sub-task 5: Automated Testing & Comprehensive Verification** - COMPLETED (Commit: `b9bd919`)
- [x] **Sub-task 6: Documentation & LLM Wiki Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 24)
- *2026-09-11*: Initialized Phase 24 per user request to display model input/output modalities (Text, Image/Vision, File/PDF, Audio/Voice, Video) in the Profile admin model selector and specifications card.
- *2026-09-11*: Leveraged OpenRouter's `architecture.input_modalities` / `architecture.output_modalities` and `models.dev`'s `modalities.input` / `modalities.output`, standardizing keys to `input_modalities` and `output_modalities`.
- *2026-09-11*: Implemented `format_modality_indicator()` helper in `hermes_catalog.py` generating compact badges (e.g. `[🖼️ Vision]`, `[💬 Text]`, `[🖼️📁 Multi]`) for select dropdowns.
- *2026-09-11*: Integrated `format_modality_indicator` into `ProfileAdminForm` option labels with empirical verification.
- *2026-09-11*: Upgraded `#hermes-model-specs-card` in `agent_profile_models.js` to render a dedicated, stylized **Accepted** and **Generated** input/output modality badge section.
- *2026-09-11*: Validated 100% test pass rate across 185 unit tests (26 in `apps.integration`, 159 across all other apps).

### 4. Current Focus
Phase 24 completed and merged into `main`.

---

## Phase 24.1: Profile Inline Compatibility, Full-Width Card Layout & Cache Busting

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 07:37:00+03:00

### 1. Objective & Scope
Fix the client-side model selector and specifications card layout in Django Admin:
- **Support Inlines & Standalone Selectors (`agent_profile_models.js`)**: Replace rigid `id_provider` / `id_model_name` lookups with dynamic pattern matching (`select.hermes-provider-select`, `select[name$="provider"]`, `select[name$="-provider"]`) so the script initializes seamlessly inside `ProfileInline` on `CustomUserAdmin` (`/admin/auth/user/`) and standalone `ProfileAdmin`.
- **Full-Width Responsive Card Layout (`agent_profile_models.js`)**: Fix the horizontal flex clipping bug where `.flex-container` pushed the card to the right by attaching the card directly to the outer `.form-row` / `.field-model_name` container with `display: block`, `width: 100%`, `box-sizing: border-box`, `clear: both`, and `margin-top: 12px`. This guarantees the card always renders on its own full-width line directly beneath the model selector with zero horizontal cut-off.
- **Browser Cache Busting (`admin.py`)**: Register absolute static paths (`/static/admin/js/agent_profile_models.js?v=24.1` and `/static/admin/js/hermes_profile_selector.js?v=24.1`) in `ProfileInline.Media`, `CustomUserAdmin.Media`, and `ProfileAdmin.Media` to bust stale browser caches without Django URL-encoding the question mark.
- **Visual & Automated Verification**: Verify via automated tests across the entire test suite (185/185 tests passing) and inspect rendered HTML outputs for both User Profile inlines and standalone Profile admin forms.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/profile-inline-model-card-fix`)
- [x] **Sub-task 2: Dynamic Inline Selector Pattern & Full-Width Card CSS (`agent_profile_models.js`)** - COMPLETED (Commit: `ab15edf`)
- [x] **Sub-task 3: Cache-Busting Versioning in Admin Media (`admin.py`)** - COMPLETED (Commit: `ab15edf`)
- [x] **Sub-task 4: Automated Testing & Visual Verification** - COMPLETED (Ran 185 tests in 112s, 100% pass rate)
- [x] **Sub-task 5: Merge into Main & Documentation Synchronization** - COMPLETED

### 3. Key Decisions & Deviations (Phase 24.1)
- *2026-09-11*: Diagnosed that `ProfileInline` on `/admin/auth/user/<id>/change/` generates IDs like `id_profile-0-provider` and `id_profile-0-model_name`. Added dynamic prefix resolution and class-based selector targeting (`.hermes-provider-select` and `.hermes-model-select`).
- *2026-09-11*: Discovered that in Django Admin, `modelSelect.parentNode` is `<div class="flex-container">`, which is a flex row. Appending `card` inside it caused the card to render side-by-side on the far right and get clipped by `.form-row`'s `overflow: hidden`. Solved by appending `card` to the outer `.form-row` container with `display: block; width: 100%; box-sizing: border-box;`, so it sits on its own row directly below the select box and help text.
- *2026-09-11*: Discovered empirically that passing relative paths with query strings (e.g. `'admin/js/agent_profile_models.js?v=24.1'`) to Django `Media.js` caused Django's `static()` helper to URL-encode `?` into `%3F`, resulting in HTTP 404. Resolved by specifying absolute paths `'/static/admin/js/agent_profile_models.js?v=24.1'`, which Django serves directly with HTTP 200 OK.
- *2026-09-11*: Added custom model preservation logic in `agent_profile_models.js`: if an existing profile has a model ID not in the catalog, it is preserved as `(Current / Custom)` rather than silently resetting to the first option.

### 4. Current Focus
Phase 24.1 completed and merged into `main`. Ready for final user validation.

---

## Phase 25: Profile-Scoped Skills Architecture & Hermes Isolation

- **Status**: COMPLETED
- **Active Branch**: `feat/profile-scoped-skills`
- **Last Updated**: 2026-09-11 08:37:00+03:00

### 1. Objective & Scope
Restructure the Hermes Agent skill layout from a flat global directory into a native profile-scoped architecture, placing specialist skills directly inside each profile's directory (`agent_service/profiles/<name>/skills/`), updating the profile provisioner, and enforcing strict skill isolation:
- **Relocate Specialist Skills**: Move `cost_monitor` to `agent_service/profiles/cost_controller/skills/` and `output_validator` to `agent_service/profiles/qa_auditor/skills/`. Keep `django_handshake` in `agent_service/skills/` as shared infrastructure.
- **Upgrade Provisioner (`scripts/provision_profiles.py`)**: Recursively synchronize `agent_service/profiles/<name>/skills/` into `/root/.hermes/profiles/<name>/skills/` and remove obsolete custom skills from the root environment so profiles strictly see only their designated skills.
- **Update Profile Personas & Skill Configs**: Declare the colocated skills in `SOUL.md` and update execution paths in `SKILL.md`.
- **Empirical Verification**: Verify with `hermes -p <profile> skills list` that `cost_controller` has `cost_monitor`, `qa_auditor` has `output_validator`, and neither can see the other's skills. Verify 100% test pass rate across the test suite.
- **Documentation Synchronization**: Update [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md), [`docs/ai_wiki/index.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/index.md), and [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md).

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/profile-scoped-skills`, Commit: `0bf4d36`)
- [x] **Sub-task 2: Relocate Skills to Profile Directories & Update SKILL.md Paths** - COMPLETED (Commit: `5d189c2`)
- [x] **Sub-task 3: Upgrade Profile Provisioner (`scripts/provision_profiles.py`)** - COMPLETED (Commit: `4b33e66`)
- [x] **Sub-task 4: Update Profile Personas (`SOUL.md`) with Explicit Tool Bindings** - COMPLETED (Commit: `b26dc3e`)
- [x] **Sub-task 5: Empirical Verification & CLI Isolation Audit** - COMPLETED (Audited with Hermes CLI, verified 100% skill isolation and script executions)
- [x] **Sub-task 6: Documentation Synchronization & Test Suite Verification** - COMPLETED (185/185 tests passing in 112s; docs/agent_team.md, index.md, and architecture.md synchronized)

### 3. Key Decisions & Deviations (Phase 25)
- *2026-09-11*: Initialized Phase 25 per user feedback regarding the separation between profiles and skills in `agent_service/`. Aligned with Hermes Agent's native design where profiles support profile-level skills under `/root/.hermes/profiles/<name>/skills/`.
- *2026-09-11*: Relocated `cost_monitor` into `agent_service/profiles/cost_controller/skills/` and `output_validator` into `agent_service/profiles/qa_auditor/skills/`. Updated usage documentation in both `SKILL.md` files (Commit: `5d189c2`).
- *2026-09-11*: Upgraded `scripts/provision_profiles.py` to recursively synchronize `agent_service/profiles/<name>/skills/` into `/root/.hermes/profiles/<name>/skills/`, purge migrated custom skills from root `/root/.hermes/skills/custom/`, and verified profile-scoped skill isolation across profiles (Commit: `4b33e66`).
- *2026-09-11*: Updated `SOUL.md` for `cost_controller` and `qa_auditor` to explicitly declare dedicated skills and execution paths (Commit: `b26dc3e`).
- *2026-09-11*: Empirically validated skill isolation using `hermes -p <profile> skills list`: verified `cost_controller` only sees `cost_monitor`, `qa_auditor` only sees `output_validator`, and neither profile clutters other profiles or root. Executed both skills successfully and verified 100% test pass rate across 185 tests.

### 4. Current Focus
Phase 25 completed and merged into `main`.

---

## Phase 26: Orchestrator Hardening, Skill Pruning & Task Decomposer

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 09:16:00+03:00

### 1. Objective & Scope
Streamline the Orchestrator profile for high token efficiency and laser-focused coordination:
- **Skill Pruning**: Opt out of 50+ irrelevant bundled skills using the `.no-bundled-skills` marker in `agent_service/profiles/orchestrator/` so it stops inheriting music, games, video, and deep-debugging tools.
- **Dedicated Profile Skill (`task_decomposer`)**: Package a dedicated profile-scoped skill under `agent_service/profiles/orchestrator/skills/task_decomposer/` with an SOP (`SKILL.md`) and CLI helper (`run.py`) to parse goals, decompose into sub-tasks, map dependencies, and assign to our 4 department heads (`cost_controller`, `qa_auditor`, `comms_agent`, `archivist`).
- **Core Toolset Discipline**: Verify that `config.yaml` locks toolsets to the essential 5 (`kanban`, `delegate`, `clarify`, `file_ops`, `terminal`), excluding heavy media/browser tools.
- **Profile Persona (`SOUL.md`)**: Bind the `task_decomposer` skill directly in `SOUL.md`.
- **Provisioner Update (`provision_profiles.py`)**: Ensure `.no-bundled-skills` is respected and bundled skills are cleaned from the profile runtime.
- **Empirical CLI Verification**: Verify `hermes -p orchestrator skills list` shows ONLY `task_decomposer` and 0 bundled skills.
- **Documentation Synchronization**: Synchronize `docs/agent_team.md`, `docs/ai_wiki/index.md`, and `docs/ai_wiki/architecture.md`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/orchestrator-hardening`, Commit: `f96c2ee`)
- [x] **Sub-task 2: Skill Pruning (`.no-bundled-skills`) & Config Locking** - COMPLETED (Commit: `1bfebe8`)
- [x] **Sub-task 3: Dedicated `task_decomposer` Skill Implementation (`SKILL.md`, `run.py`)** - COMPLETED (Commit: `d7d80b5`)
- [x] **Sub-task 4: Profile Persona (`SOUL.md`) Binding & Provisioner Support** - COMPLETED (Commit: `b0744c3`)
- [x] **Sub-task 5: Empirical Verification & CLI Isolation Audit** - COMPLETED (Verified `0 builtin, 1 local — task_decomposer`; passed 185/185 unit tests in 110s)
- [x] **Sub-task 6: Documentation Synchronization & Test Suite Verification** - COMPLETED (Commit: `86343c7`)

### 3. Key Decisions & Deviations (Phase 26)
- *2026-09-11*: Initialized Phase 26 per user discussion regarding Orchestrator's role, token efficiency, and toolsets. Confirmed that enabling all toolsets is an anti-pattern and that Orchestrator should only have the 5 core toolsets and planning skills.
- *2026-09-11*: Added `.no-bundled-skills` marker in `agent_service/profiles/orchestrator/` to prune 54 built-in bundled Hermes skills, saving thousands of tokens per prompt turn. Locked `config.yaml` and `profile.yaml` to the 5 core toolsets (`kanban`, `delegate`, `clarify`, `file_ops`, `terminal`).
- *2026-09-11*: Implemented `task_decomposer` profile skill in `agent_service/profiles/orchestrator/skills/task_decomposer/` with DAG cycle validation, department pipeline sequencing, and Django REST API task submission (`POST /api/tasks/`).
- *2026-09-11*: Updated `SOUL.md` with explicit tool bindings and updated `scripts/provision_profiles.py` to sync `.no-bundled-skills` and purge unassigned bundled skills from profile runtimes.
- *2026-09-11*: Empirically validated with Hermes CLI: `hermes -p orchestrator skills list` confirms `0 hub-installed, 0 builtin, 1 local — 1 enabled, 0 disabled` (only `task_decomposer`). Ran `task_decomposer` dry-run successfully.
- *2026-09-11*: Executed complete backend test suite: 185/185 tests passing in 110.497s. Synchronized `docs/agent_team.md`, `docs/ai_wiki/index.md`, and `docs/ai_wiki/architecture.md`.

### 4. Current Focus
Phase 26 completed and merged into `main`.

---

## Phase 27: Cost Controller Hardening, Toolset Locking & Frontier Benchmark Intelligence (DeepSWE)

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 10:18:00+03:00

### 1. Objective & Scope
Harden the `cost_controller` profile and establish automated model benchmark intelligence:
- **Skill Pruning & Toolset Locking**: Add `.no-bundled-skills` to `agent_service/profiles/cost_controller/`, locking toolsets strictly to `[terminal, file_ops]` in `config.yaml` and `profile.yaml`.
- **ModelBenchmark Relational Model (`apps.integration`)**: Create `ModelBenchmark` table and add `recommendations` field to `SpendReport` to store data-driven model switching advice.
- **Automated Benchmark Ingestion Service**: Build `benchmark_sync.py` to ingest DeepSWE scores and pricing into PostgreSQL with fail-safe caching and zero shadow AI.
- **REST API & Admin Portal**: Expose `GET /api/hermes/benchmarks/` and register `ModelBenchmarkAdmin` with colored pass-rate badges and manual sync action.
- **Upgrade `cost_monitor` Skill**: Enhance `run.py` to evaluate Intelligence-per-Dollar ROI ($ROI = \text{score} / \text{cost}$), print optimization suggestions, and push them to Django `SpendReport`.
- **Empirical Verification & Testing**: Verify `hermes -p cost_controller skills list` shows 0 builtin skills, test `cost_monitor` script, and verify 100% test pass rate across all backend unit tests.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/cost-controller-hardening-and-benchmarks`, Commit: `fec2ef3`)
- [x] **Sub-task 2: Skill Pruning (`.no-bundled-skills`), Toolset Locking & SOUL.md Update** - COMPLETED (Commit: `fb3c8aa`)
- [x] **Sub-task 3: Django ModelBenchmark Model, Migration & Ingestion Service** - COMPLETED (Commit: `3341075`)
- [x] **Sub-task 4: Upgrade `cost_monitor` with Benchmark Optimization Engine** - COMPLETED (Commit: `ee65926`)
- [x] **Sub-task 5: Profile Provisioning & Empirical CLI Isolation Verification** - COMPLETED (Verified `0 builtin, 1 local — cost_monitor`, pushed spend report HTTP 201, 187/187 tests passed in 110s)
- [x] **Sub-task 6: Documentation Synchronization, Test Suite Verification & Merge** - COMPLETED

### 3. Key Decisions & Deviations (Phase 27)
- *2026-09-11*: Initialized Phase 27 per user discussion on frontier benchmark tracking (DeepSWE). Agreed on the hybrid architecture: Django handles data plumbing/storage with zero AI overhead (preventing shadow token spend), while `cost_controller` accesses the data to deliver model ROI recommendations. Locked `cost_controller` toolsets to `[terminal, file_ops]`.
- *2026-09-11*: Added `.no-bundled-skills` to `agent_service/profiles/cost_controller/` pruning 54 bundled Hermes skills, and locked `config.yaml` / `profile.yaml` to `[terminal, file_ops]`.
- *2026-09-11*: Created `ModelBenchmark` model and `benchmark_sync.py` ingestion service in `apps.integration`, exposed `GET /api/hermes/benchmarks/`, and registered `ModelBenchmarkAdmin`.
- *2026-09-11*: Upgraded `cost_monitor/run.py` to query Django benchmarks, compute Intelligence-per-Dollar ROI, and format automated model-switching recommendations pushed to Django `SpendReport`.
- *2026-09-11*: Provisioned profiles, empirically verified CLI isolation with `hermes -p cost_controller skills list` (`0 builtin, 1 local`), and ran full test suite: 187/187 unit tests passing in 110.489s.

### 4. Current Focus
Phase 27 completed and merged into `main`.

---

## Phase 28: QA Auditor Hardening, Skill Pruning & Review Gate Integration

- **Status**: COMPLETED
- **Active Branch**: `feat/qa-auditor-hardening`
- **Last Updated**: 2026-09-11 11:02:00+03:00

### 1. Objective & Scope
Harden the `qa_auditor` profile to eliminate prompt token bloat, enforce strict review toolset discipline, and enhance the `output_validator` skill with automated Django review gate verdict submission:
- **Skill Pruning**: Opt out of 54 irrelevant bundled skills using `.no-bundled-skills` in `agent_service/profiles/qa_auditor/` so it stops inheriting music, games, p5js, media, and unneeded tools.
- **Toolset Locking**: Lock toolsets strictly to `[kanban, terminal, file_ops]` in both `config.yaml` and `profile.yaml`, maintaining `reasoning_effort: high`.
- **Review Gate Integration (`output_validator`)**: Upgrade `agent_service/profiles/qa_auditor/skills/output_validator/run.py` to support `--submit` and `--task-id <UUID>` CLI arguments, programmatically sending the audit verdict (`approved` / `changes_requested`), score, and feedback notes to Django's review gate (`POST /api/tasks/<id>/submit-verdict/`) using `bot_qa_auditor`'s API token.
- **Profile Persona (`SOUL.md`)**: Update `SOUL.md` to reflect the locked toolsets and document the upgraded `--submit` workflow.
- **Provisioner Synchronization (`scripts/provision_profiles.py`)**: Synchronize `.no-bundled-skills` and the upgraded skill into the container runtime and purge unneeded bundled skills.
- **Empirical Verification & Testing**: Verify `hermes -p qa_auditor skills list` confirms `0 builtin, 1 local — output_validator`, test `output_validator` end-to-end against a test task, and confirm 100% test pass rate across all backend unit tests.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/qa-auditor-hardening`, Commit: `92cbb46`)
- [x] **Sub-task 2: Skill Pruning (`.no-bundled-skills`), Toolset Locking & SOUL.md Update** - COMPLETED (Commit: `fdb76a2`)
- [x] **Sub-task 3: Upgrade `output_validator` with Direct Review Gate Submission** - COMPLETED (Commit: `1c68355`)
- [x] **Sub-task 4: Profile Provisioning & Empirical CLI Isolation Verification** - COMPLETED (Verified `0 builtin, 1 local — output_validator`)
- [x] **Sub-task 5: Comprehensive Automated Testing & End-to-End Task Review Verification** - COMPLETED (Verified review verdict API submission; 187/187 tests passing in 112s)
- [x] **Sub-task 6: Documentation Synchronization, Test Suite Verification & Merge** - COMPLETED

### 3. Key Decisions & Deviations (Phase 28)
- *2026-09-11*: Initialized Phase 28 per user approval. Aligned with the hardening architecture established in Phase 26 (Orchestrator) and Phase 27 (Cost Controller).
- *2026-09-11*: Added `.no-bundled-skills` to `agent_service/profiles/qa_auditor/`, successfully pruning 54 bundled Hermes skills and saving thousands of tokens per turn. Locked toolsets strictly to `[kanban, terminal, file_ops]` in `config.yaml` and `profile.yaml`.
- *2026-09-11*: Upgraded `output_validator` with `--submit --task-id <UUID>` CLI flags to bridge the Hermes CLI audit with Django's RBAC review gate (`POST /api/tasks/<id>/submit-verdict/`), completing the autonomous review loop with `bot_qa_auditor` credentials.
- *2026-09-11*: Empirically validated skill isolation using `hermes -p qa_auditor skills list`: verified `0 hub-installed, 0 builtin, 1 local — output_validator`. Tested end-to-end against an `AgentTask` in `review` status, verifying automatic transition to `completed` and clean notes persistence.
- *2026-09-11*: Executed complete backend test suite: 187/187 tests passing in 112.692s. Synchronized `docs/agent_team.md`, `docs/ai_wiki/index.md`, and `docs/plans/active_plan.md`.

### 4. Current Focus
Phase 28 completed and merged into `main`.

---

## Phase 29: Client Service & Communications Coordinator Hardening, Skill Pruning & Budgeted Concierge Bridge

- **Status**: COMPLETED
- **Active Branch**: `feat/client-service-and-budget-bridge`
- **Last Updated**: 2026-09-11 12:20:00+03:00

### 1. Objective & Scope
Transform and harden `comms_agent` from a narrow communications/scheduler role into an enterprise **Client Service & Communications Coordinator**:
- **3-Tier Hierarchy & Zero-Trust File Security**:
  - Firm/Tenant level (`apps.tenants`) $\rightarrow$ Business Module level $\rightarrow$ External Clients (`Profile.user_type = 'client'`).
  - Strict zero-trust data access: `backend/media` is **never mounted into Hermes**. All file reads occur via authenticated Django REST endpoints (`GET /api/v1/media/documents/<id>/download/`) with tenant/client ownership validation and SOC2/GDPR audit logging (`apps.audit`).
  - Client uploads use standard `POST /upload/` multipart endpoints, and transient Hermes files are immediately purged (`os.unlink()`).
- **Percentage-Based Dollar AI Budget Governance (Cost Controller)**:
  - Replace rigid message counters with dollar-denominated percentage thresholds against each client's allocated budget (25% silent audit, 50% velocity check, 75% proactive advisory notice, 100% quota escalation).
- **Skill Pruning & Toolset Locking**:
  - Add `.no-bundled-skills` to `agent_service/profiles/comms_agent/` to prune 54 bundled skills.
  - Lock toolsets strictly to `[terminal, file_ops]` in `config.yaml` and `profile.yaml`.
  - Maintain `reasoning_effort: none` for zero thinking latency and lowest-cost execution.
  - Update `SOUL.md` to establish client concierge principles.
- **Dedicated Profile Skill (`client_service_bridge`)**:
  - Implement `client_service_bridge` supporting client status queries, document inventories, secure REST streaming downloads, multi-channel outbound notification dispatches (`apps.notifications`), and budget milestone audits.
- **Empirical Verification & Testing**:
  - Verify skill isolation via Hermes CLI (`0 builtin, 1 local — client_service_bridge`).
  - Verify `client_service_bridge` modes against Django backend.
  - Verify 100% test pass rate across backend test suite.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/client-service-and-budget-bridge`, Commit: `bc19304`)
- [x] **Sub-task 2: Django Backend Client Budgeting & Scoping (`apps.integration`)** - COMPLETED (Commit: `5ee23aa`)
- [x] **Sub-task 3: Profile Skill Pruning (`.no-bundled-skills`), Toolset Locking & SOUL.md Update** - COMPLETED (Commit: `57aedaa`)
- [x] **Sub-task 4: Dedicated `client_service_bridge` Skill Implementation** - COMPLETED (Commit: `5dc1544`)
- [x] **Sub-task 5: Profile Provisioning & Empirical CLI Isolation Verification** - COMPLETED (Verified `0 hub-installed, 0 builtin, 1 local — client_service_bridge`)
- [x] **Sub-task 6: End-to-End Verification, Automated Testing & Merge** - COMPLETED (Verified live CLI modes, 188/188 backend tests pass 100% in 117s)

### 3. Key Decisions & Deviations (Phase 29)
- *2026-09-11*: Initialized Phase 29 per user approval. Renamed and elevated role to **Client Service & Communications Coordinator**.
- *2026-09-11*: Rejected shared media volume mount per user's security direction; implemented Zero-Trust REST API file streaming with tenant/client ownership verification and audit trail.
- *2026-09-11*: Adopted 4-tier percentage dollar milestones (25%, 50%, 75%, 100%) governed by Cost Controller instead of rigid message counts.
- *2026-09-11*: Added `.no-bundled-skills` to `agent_service/profiles/comms_agent/`, locked toolsets strictly to `[terminal, file_ops]`, and retained `reasoning_effort: none` for zero-latency, lowest-cost external concierge operations.
- *2026-09-11*: Verified live skill isolation via `docker exec hermes-template-agent hermes -p comms_agent skills list` confirming 0 builtin skills and 1 dedicated local skill (`client_service_bridge`).
- *2026-09-11*: Verified full backend test suite: 188/188 tests passing in 117.014s with 100% pass rate.

### 4. Current Focus
Phase 29 completed and merged into `main`.

---

## Phase 30: Dedicated Client Management Module (`apps.clients`), 1-to-Many Users & AI Service Governance

- **Status**: COMPLETED
- **Active Branch**: `feat/client-management-module`
- **Last Updated**: 2026-09-11 12:48:00+03:00

### 1. Objective & Scope
Transform external client management into an independent, dedicated Django application (`apps.clients`) fulfilling the enterprise 3-tier hierarchy (Tenant $\rightarrow$ Client $\rightarrow$ Users):
- **Tenant Isolation**: Each `Client` strictly belongs to an `Organization` (`apps.tenants`).
- **1-to-Many User Association**: A single `Client` represents an external business account and links multiple user profiles (`Profile.client`).
- **AI Service Gatekeeper & Dollar Budget**:
  - `is_ai_enabled`: Master boolean flag controlling whether the client is authorized for AI assistance.
  - `ai_budget_usd` & `ai_spend_usd`: Dollar budget ceiling and real-time usage tracking.
  - Computed milestones: `healthy`, `velocity_check` (50%), `warning` (75%), `exceeded` (100%).
- **Dedicated Standalone Django Admin Dashboard**:
  - Top-level sidebar entry: **CLIENT MANAGEMENT $\rightarrow$ Clients**.
  - Dynamic visual CSS progress gauge (Green $\rightarrow$ Yellow $\rightarrow$ Red).
  - Inlines: `ClientUserInline` (manage client users directly on the client page) and `GenericDocumentInline` (attachments via `apps.media`).
- **Bridge & Coordinator Alignment**:
  - Update `client_budget_status` and `client_service_bridge` to evaluate against `apps.clients.models.Client`.
  - Reaffirm single-agent touchpoint: Clients interact exclusively through `comms_agent`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Git Branching & Active Plan Initialization** - COMPLETED (Branch: `feat/client-management-module`, Commit: `7c6199d`)
- [x] **Sub-task 2: Create `apps.clients` App, Data Models & Database Migrations** - COMPLETED (Commit: `828a7ce`)
- [x] **Sub-task 3: Link `Profile.client` in `apps.integration` & Migration** - COMPLETED (Commit: `2e02d28`)
- [x] **Sub-task 4: Dedicated Standalone Django Admin Dashboard (`apps.clients.admin`)** - COMPLETED (Commit: `d2d9bd3`)
- [x] **Sub-task 5: REST APIs, Serializers & Views (`/api/v1/clients/` & updated budget endpoint)** - COMPLETED (Commit: `1e249dc`)
- [x] **Sub-task 6: Update `client_service_bridge` Skill & Comprehensive Automated Testing** - COMPLETED (Commit: `a399096`)
- [x] **Sub-task 7: Documentation Synchronization, Full Test Suite Verification & Merge** - COMPLETED (197/197 tests passing in 118.9s)

### 3. Key Decisions & Deviations (Phase 30)
- *2026-09-11*: Initialized Phase 30 per user direction. Extracted clients from a generic user profile attribute into a standalone first-class `apps.clients` app.
- *2026-09-11*: Enforced 1-to-many relationship: an Organization has multiple Clients, and each Client can have multiple Users (`Profile.client`).
- *2026-09-11*: Implemented dynamic visual CSS progress gauge in Django Admin sidebar for `ClientAdmin`, with embedded `ClientUserInline` and `GenericDocumentInline`.
- *2026-09-11*: Upgraded `client_service_bridge` and `client_budget_status` API to resolve directly against `Client` with `is_ai_enabled` gatekeeper verification.
- *2026-09-11*: Verified full backend test suite: 197/197 tests passing in 118.900s with 100% pass rate.

### 4. Current Focus
Phase 30 completed and merged into `main`. Transitioning to Phase 31.

---

## Phase 31: Retire Archivist & Promote Security Guard as 5th Core Department Head

- **Status**: IN_PROGRESS
- **Active Branch**: `feat/security-guard-core-profile`
- **Last Updated**: 2026-09-11 13:05:00+03:00

### 1. Objective & Scope
Retire the legacy, redundant `archivist` profile (whose documentation responsibilities are already handled automatically by Antigravity IDE agent rules) and establish **Security Guard / Security Auditor (`security_guard`)** as the official 5th core department head across Django and Hermes:
- **Clean Database & Runtime Retirement of Archivist**:
  - Safely delete `bot_archivist` user, `Agent_Archivist` group, and legacy `archivist` profile from Django PostgreSQL database.
  - Delete `agent_service/profiles/archivist/` from the repository and purge `/root/.hermes/profiles/archivist` from Hermes container runtime.
- **Elevate & Harden `security_guard` as 5th Department Head**:
  - Add `'security'` to `Profile.ROLE_CHOICES` in `backend/apps/integration/models.py`.
  - Update `seed_profiles.py` with canonical `security_guard` profile, `Agent_SecurityGuard` group, and permissions (`view_agenttask`, `view_profile`, `view_activitylog`, `view_apikey`, `view_webhookevent`).
  - Lock toolsets strictly to `[terminal, file_ops]` in `config.yaml` and `profile.yaml`, configure `reasoning_effort: high`, add `.no-bundled-skills` to prune 54 bundled skills, and draft an authoritative zero-trust `SOUL.md`.
- **Dedicated Profile-Scoped Skill (`security_scanner`)**:
  - Implement multi-mode CLI script `agent_service/profiles/security_guard/skills/security_scanner/run.py` supporting `secrets-scan`, `tenant-audit`, `rbac-audit`, `gateway-audit`, and structured JSON export.
  - Document SOP in `SKILL.md`.
- **Orchestrator Hardening & Automation Presets**:
  - Update `agent_service/profiles/orchestrator/skills/task_decomposer/run.py` and `SKILL.md` to route security and permission audits to `security_guard`.
  - Update `backend/apps/automation/registry.py` prompt presets for `security_guard` and triage actions.
- **Empirical Verification & Testing**:
  - Verify Hermes CLI profile listing and skill isolation (`0 builtin, 1 local — security_scanner`).
  - Verify 100% test pass rate across all backend unit tests.
  - Synchronize `docs/agent_team.md`, `docs/ai_wiki/index.md`, and `docs/ai_wiki/architecture.md`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Active Plan Initialization & Git Branching** - COMPLETED (Branch: `feat/security-guard-core-profile`)
- [x] **Sub-task 2: Django Backend Integration, Model Choices & Clean Retirement of Archivist (`seed_profiles.py` & `models.py`)** - COMPLETED (Commit: `40f951b`)
- [x] **Sub-task 3: Centralized Automation Registry Presets & Triage Updates (`registry.py`)** - COMPLETED (Commit: `pending`)
- [x] **Sub-task 4: Profile Hardening, Toolset Locking & Skill Implementation (`security_guard` & `security_scanner`)** - COMPLETED
- [x] **Sub-task 5: Orchestrator Hardening & Task Decomposer Update (`task_decomposer`)** - COMPLETED
- [x] **Sub-task 6: Automated Profile Provisioner Upgrade (`provision_profiles.py`) & Empirical Container Verification** - COMPLETED
- [x] **Sub-task 7: Comprehensive Automated Testing, Documentation Synchronization & Merge** - COMPLETED (198/198 unit tests passing in 112s)

### 3. Key Decisions & Deviations (Phase 31)
- *2026-09-11*: Initialized Phase 31 per user instruction to retire `archivist` (whose responsibilities are already handled by Antigravity IDE rules) and elevate `security_guard` to the official 5th core department head.
- *2026-09-11*: Added `'security'` to `Profile.ROLE_CHOICES` in `apps.integration.models`, applied migration `0013_alter_profile_role`.
- *2026-09-11*: Updated `seed_profiles.py` to seed `security_guard` (`Security & Threat Auditor`, role `security`, `reasoning_effort: high`) and create `Agent_SecurityGuard` with permissions (`view_agenttask`, `view_profile`, `view_activitylog`, `view_apikey`, `view_webhookevent`). Added automatic retirement logic that cleanly purged legacy `bot_archivist`, `Agent_Archivist` group, and `archivist` profile from PostgreSQL.
- *2026-09-11*: Replaced `archivist` prompt presets in `apps.automation.registry` with 4 production SecOps presets for `security_guard` (secrets leak scan, multi-tenant boundary check, webhook/auth threat audit, comprehensive posture scan) and updated `orchestrator`'s triage preset.
- *2026-09-11*: Hardened `agent_service/profiles/security_guard/` with `.no-bundled-skills` (pruning 54 bundled skills), toolset locking to `[terminal, file_ops]`, calibrated `high` reasoning, and an authoritative zero-trust `SOUL.md`.
- *2026-09-11*: Implemented dedicated profile-scoped skill `security_scanner` (`run.py` & `SKILL.md`) supporting multi-mode scans: regex-based secret leak detection (OpenAI, OpenRouter, Anthropic, Stripe, SSH/RSA private keys), model tenant isolation checks, RBAC least privilege verification, and API gateway threat posture. Added `--exclude-tests` and `--json` support.
- *2026-09-11*: Upgraded `task_decomposer` in `orchestrator` (`run.py`, `SKILL.md`, `SOUL.md`) to replace `archivist` with `security_guard` and route security audits as step 4 before client handoff.
- *2026-09-11*: Upgraded `scripts/provision_profiles.py` with automated container runtime retirement logic, purging `/root/.hermes/profiles/archivist` and provisioning all 5 core profiles.
- *2026-09-11*: Empirically validated via Hermes CLI: `hermes -p security_guard skills list` confirms `0 hub-installed, 0 builtin, 1 local — security_scanner`. Executed `security_scanner` and `task_decomposer` inside the Hermes container with exit code 0.
- *2026-09-11*: Validated 100% test pass rate across all 198 unit tests in the entire backend test suite.
- *2026-09-11*: Clarified functional boundaries between `qa_auditor` and `security_guard` (Option A): `qa_auditor` (`output_validator`) serves as the syntactic compiler and deliverable hygiene gatekeeper with a lightweight pre-commit leak seatbelt; `security_guard` (`security_scanner`) governs enterprise SecOps, multi-tenant boundary isolation, RBAC least privilege, and API gateway threat monitoring. Synchronized documentation across `agent_team.md`, `index.md`, and `architecture.md`.

### 4. Current Focus
Phase 31 completed and merged into `main`. Ready for next directives.

---

## Phase 32: Client-Dedicated Physical Storage & First-Class Document Architecture

- **Status**: COMPLETED <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `main`
- **Last Updated**: 2026-09-11 14:15:00+03:00

### 1. Objective & Scope
Transform client document storage from a generic, hash-sharded scheme into a clean, human-readable, domain-driven structure:
1. Elevate `client` to an explicit, indexed Foreign Key on `apps.media.models.Document` (`client_id`) with bidirectional sync to Django's `GenericForeignKey`.
2. Automatically create dedicated physical storage directories (`documents/clients/<client_id>/`) on disk upon `Client` creation.
3. Route uploaded client files directly to `documents/clients/<client_id>/<filename>`.
4. Clean up legacy test folders from `backend/media/documents/` and isolate test suites using temporary directories for `MEDIA_ROOT`.
5. Expose `client` / `client_id` across DRF serializers, viewsets, and Django Admin.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Media Model & Storage Path Refactor** - COMPLETED
- [x] **Sub-task 2: Automatic Client Directory Provisioning** - COMPLETED
- [x] **Sub-task 3: API & Admin Synchronization** - COMPLETED
- [x] **Sub-task 4: Media Cleanup & Test Suite Isolation** - COMPLETED
- [x] **Sub-task 5: Empirical Verification & Documentation Synchronization** - COMPLETED (Commit: `c2f4ea6`)

### 3. Key Decisions & Deviations
- *2026-09-11*: Opted for Option A (explicit `client = models.ForeignKey(Client, ...)` on `Document`) with dual-synchronization in `Document.save()` to maintain full backwards compatibility with Django `GenericForeignKey` queries (`content_type` + `object_id`).
- *2026-09-11*: Structured client document physical storage as `documents/clients/<client_id>/<filename>`. Because `client_id` is a UUIDv4, it guarantees global uniqueness without folder name collisions.
- *2026-09-11*: Configured ephemeral test media directories (`tempfile.mkdtemp()`) across test suites in `apps.media` and `apps.clients` with automated `tearDownModule()` teardowns, eliminating persistent test clutter in the host `media/` folder.

### 4. Current Focus
Phase 32 completed and verified (205/205 tests passing 100%). Transitioning to Phase 33.

---

## Phase 33: Enterprise React Frontend: Apple-Style Shell, Multi-Modal AI Studio & Odoo-Style Settings

- **Status**: COMPLETED
- **Active Branch**: `feat/enterprise-react-frontend`
- **Last Updated**: 2026-09-12 04:47:00+03:00

### 1. Objective & Scope
Build a modern, containerized **React** frontend platform for the Universal AI System Template:
- **Dockerized Container Architecture (`frontend/`)**: Containerize React 18 + Vite SPA using `node:20-alpine` on port 3000, connected to backend network with hot module reloading.
- **Apple-Style Platform Shell**:
  - Top taskbar with dynamic, reorderable menus and submenus, system status, global search launcher (`Cmd+K`), notification bell, and user profile avatar.
  - Fullscreen Launchpad springboard with reorderable/draggable application icons and search filtering.
  - Quick-access dock for pinned applications.
- **Enterprise Multi-Modal AI Chat Studio (`src/apps/ai_studio/`)**:
  - Voice-first interface: live speech-to-text audio detection and voice message recording.
  - Multi-modal attachments (Video, Audio, Images, Documents/PDFs) with dynamic validation against model modality badges (`[🖼️ Vision]`, `[📁 PDF]`, `[🎙️ Audio]`, `[🎥 Video]`).
  - Model control bar: instant switching between the 5 Department Heads (`orchestrator`, `cost_controller`, `qa_auditor`, `comms_agent`, `security_guard`), provider dropdown, model selector with context window metrics, and reasoning effort slider (`none`, `low`, `medium`, `high`, `max`).
  - Real-time CLI-grade telemetry: live token counter (prompt + completion = total), real-time cost calculation ($ USD) using catalog token rates, generation speed (tokens/sec), and collapsible reasoning thought-blocks.
- **Odoo-Style Unified Settings Hub (`src/apps/settings/`)**:
  - Single-screen configuration center with categorized left sidebar (General, Navigation & UI, AI Models & Provider Credentials, Clients, Automations, Storage, Security).
  - Contextual jumping: direct shortcut from any app to its dedicated configuration tab in Settings.
- **Pluggable Modular App Registry & Schema Auto-Scaffolder**:
  - Drop-in modular architecture (`src/apps/<name>/` with `manifest.js`, `menus.js`, `settings.js`, `pages/`).
  - Universal generic table and form generator from DRF API options for zero-code automatic scaffolding of future domain apps (e.g., Accounting).
- **First-Class Operational Apps**:
  - Client CRM workspace (`apps/clients/`) with dynamic visual CSS budget gauges.
  - Task Registry & Review Pipeline (`apps/tasks/`).

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Docker Containerization & React + Vite Scaffolding (`frontend/`)** - COMPLETED (Commit: `2b1b76b`)
- [x] **Sub-task 2: Apple-Grade Design System, Tokens, Glassmorphism & RTL Support (`index.css`)** - COMPLETED (Commit: `63718a2`)
- [x] **Sub-task 3: Apple-Style Platform Shell (TopBar, Menus, Launchpad Springboard & Dock)** - COMPLETED (Commit: `8a7ad69`)
- [x] **Sub-task 4: Pluggable App Registry & Schema-Driven Auto-Scaffolder** - COMPLETED (Commit: `8a7ad69`)
- [x] **Sub-task 5: Enterprise Multi-Modal AI Chat Studio (Voice, Media, Telemetry, Controls)** - COMPLETED (Commit: `8a7ad69`)
- [x] **Sub-task 6: Odoo-Style Unified Settings Hub & App Tab Integrations** - COMPLETED (Commit: `8a7ad69`)
- [x] **Sub-task 7: Operational Workspaces (Clients CRM & AI Tasks)** - COMPLETED (Commit: `8a7ad69`)
- [x] **Sub-task 8: End-to-End Verification, Automated Testing & Documentation Synchronization** - COMPLETED (Commit: `docs`)

### 3. Key Decisions & Deviations (Phase 33)
- *2026-09-12*: Initialized Phase 33 per user directive to build a containerized React frontend.
- *2026-09-12*: Selected Apple-style platform shell metaphor (top taskbar with dynamic submenus, fullscreen glassmorphic Launchpad springboard with reorderable app icons) combined with an Odoo-style single-screen Settings Hub with categorized sidebar.
- *2026-09-12*: Designed the AI Chat Studio as a voice-first, multi-modal workspace (speech detection, video/audio/doc uploads) with live CLI-style telemetry (real-time token counters, generation speed, and cost calculation in $ USD).
- *2026-09-12*: Adopted 2-tier hybrid extensibility: Pluggable modular apps (`src/apps/`) + Universal schema-driven CRUD scaffolder for zero-code future domain applications.
- *2026-09-12*: Implemented `frontend/` Docker setup on port 3000 with hot-module reloading and production build testing (`npm run build` passing in 3.33s).
- *2026-09-12*: Verified full backend test suite: 205/205 tests passing in 117s (100% pass rate).
- *2026-09-12*: **UX & Navigation Refinement**: Per user direction, restructured the landing page to follow Odoo's clean architecture (central App Grid right in the middle of the screen as the main home view) with Apple visual squircle aesthetics. Completely removed the bottom dock to avoid interface clutter. Repositioned AI Chat Studio as an internal module rather than the default landing page. Integrated a pluggable Theme Engine (`themeEngine.js`) supporting multiple switchable themes (`Apple Obsidian Glass`, `Apple Frosted Light`, `Odoo Enterprise Purple`, `Cyber Emerald Pro`) with 1-click switching from TopBar and Settings.

### 4. Current Focus
Phase 33 completed and verified. Transitioning to Phase 34 per user directive.

---

## Phase 34: Full Two-Way Frontend <-> Django Integration & Live Data Binding

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-12 06:36:00+03:00

### 1. Objective & Scope
Completely connect the React frontend SPA to the live Django backend so that all tables, metric gauges, forms, and configuration settings represent and mutate real records in PostgreSQL, mapped directly to Django Admin:
- **Authentication & Workspace Bridge**:
  - Expose `/api/token-auth/`, `/api/auth/token/`, and `/api/auth/me/`.
  - Issue/seed a valid DRF Token for `admin` and connect `authContext` to live backend sessions.
  - Automatically pass `Authorization: Token <token>` and `X-Workspace-Slug: <slug>`.
- **Two-Way Client Management (`apps/clients/`)**:
  - Live query `GET /api/v1/clients/` with real-time budget metric gauges.
  - Interactive "New Record" modal submitting `POST /api/v1/clients/`.
  - Client detail view with budget overrides (`POST .../budget-status/`) and document/user associations.
- **Two-Way Task Kanban Pipeline (`apps/tasks/`)**:
  - Live query `GET /api/tasks/` across pending, in-progress, review, and completed columns.
  - "New Task" creation modal submitting `POST /api/tasks/`.
  - Interactive QA gate review verdict submission (`POST /api/tasks/<id>/submit-verdict/`).
- **Live Settings & Provider Credentials (`apps/settings/`)**:
  - Expose `/api/provider-credentials/` for live viewing, adding, and toggling LLM API keys.
  - Expose `/api/settings/` to persist and retrieve general branding settings (`AppSettingValue`).
- **Live TopBar Notifications & Workspaces (`shell/TopBar.jsx`)**:
  - Real-time unread notification count and dropdown via `/api/v1/notifications/`.
  - Live organization list and switching via `/api/v1/organizations/`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Django Admin Model Audit & Implementation Plan** - COMPLETED (All 25+ models audited; implementation plan approved)
- [x] **Sub-task 2: Backend Auth, Provider Credentials & Settings API Endpoints** - COMPLETED (`CustomObtainAuthToken`, `CurrentUserView`, `AppSettingsView`, `ProviderCredentialViewSet`)
- [x] **Sub-task 3: Frontend Live Token Authentication & Session Integration** - COMPLETED (`authContext.jsx` auto-bootstraps real token, discards dev-token, verifies with `/api/auth/me/`)
- [x] **Sub-task 4: Two-Way Client Management & Form Submission** - COMPLETED (Live `GET /api/v1/clients/`, `POST /api/v1/clients/` with automatic slug & org assignment; fixed Vite proxy `ALLOWED_HOSTS` 400 error)
- [x] **Sub-task 5: Two-Way Task Kanban & QA Verdict Submission** - COMPLETED (`TaskWorkspace.jsx` query & create tasks, QA review verdicts via `/api/tasks/`)
- [x] **Sub-task 6: Live Settings Hub, Credentials & TopBar Notifications** - COMPLETED (Live settings and credentials management; TopBar real-time unread notifications bell and dropdown)
- [x] **Sub-task 7: Full System Verification, E2E Form Testing & Commit** - COMPLETED (205/205 backend tests pass 100%, frontend production build passes cleanly, Vite proxy verified with HTTP 201; Commit: `bd54eed`)

### 3. Key Decisions & Deviations (Phase 34)
- *2026-09-12*: User directed prioritizing full end-to-end two-way data integration with Django before further UI feedback.
- *2026-09-12*: Audited all 25+ models in Django Admin and established exact 1-to-1 mappings into frontend workspaces.
- *2026-09-12*: **Vite Proxy & Host Header Root Cause (400 Bad Request)**: Server container logs revealed `DisallowedHost: Invalid HTTP_HOST header: 'django-template-backend:8000'`. Vite's `changeOrigin: true` proxies to the internal Docker container name `django-template-backend:8000`, which was absent from Django's `ALLOWED_HOSTS`. Added `django-template-backend` and wildcard `*` during `DEBUG=True` in both `core/settings.py` and `.env`. Verified with curl through port 3000 returning HTTP 201 Created.
- *2026-09-12*: Discontinued browser agent automation per user directive; user will test the live UI directly in their browser.

### 4. Current Focus
Phase 34 completed and verified.

---

## Phase 35: Authentication Gate, CSRF Trusted Origins & Django Admin Navigation

- **Status**: COMPLETED
- **Active Branch**: `main`
- **Last Updated**: 2026-09-12 06:55:00+03:00

### 1. Objective & Scope
Address Notes 1, 2, and 3 from user feedback:
- **Note 1 (Authentication Gate & Login Page)**: Provide dedicated `LoginPage.jsx` component, guard root navigation in `App.jsx`, support explicit user logout with session clearing, and offer 1-click admin login.
- **Note 2 (CSRF Trusted Origins)**: Configure `CSRF_TRUSTED_ORIGINS` in `backend/core/settings.py` and `.env` to trust `http://localhost:3000`, `http://127.0.0.1:3000`, and `http://localhost:8000`.
- **Note 3 (Django Admin Navigation & Vite Proxy)**: Route Django Admin directly to backend port 8000 in `TopBar.jsx` and configure `/admin` and `/static` reverse proxy rules in `frontend/vite.config.js`.

### 2. Task Checklist & Progress
- [x] **Sub-task 1: Django CSRF Trusted Origins Configuration** - COMPLETED
- [x] **Sub-task 2: Django Admin Navigation & Vite Proxy for `/admin` & `/static`** - COMPLETED
- [x] **Sub-task 3: Dedicated `LoginPage.jsx`, Authentication Guard & Logout Lifecycle** - COMPLETED
- [x] **Sub-task 4: Frontend Compilation & Live Endpoints Verification** - COMPLETED (Commit: `593b074`)

### 3. Key Decisions & Deviations (Phase 35)
- *2026-09-12*: Implemented `LoginPage` with theme support (EN/AR), status indicator, and quick-login shortcut for development.
- *2026-09-12*: Added `is_logged_out` flag in `sessionStorage` upon clicking Logout, preventing automatic background admin re-authentication so the user remains on the login page until explicitly signing in.
- *2026-09-12*: Configured both Vite proxy (`/admin`, `/static`) and dynamic direct port resolution (`:8000/admin/`) to guarantee reliable access to Django Admin regardless of entry path.

### 4. Current Focus
Phase 35 completed. Ready for user browser verification.

---

## Phase 36: Enterprise Agent Upgrade & Self-Refining Platform (PENDING REVIEW)

- **Status**: PENDING <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `main`
- **Last Updated**: 2026-09-13 13:14:00+03:00
- **Dedicated Implementation Plan**: [`docs/plans/enterprise_agent_upgrade_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/enterprise_agent_upgrade_plan.md)

### 1. Objective & Scope
Transform Hermes Agent into a **Sovereign, 100% Standalone AI Agent Platform** (`agent_service/`) completely decoupled from the Django backend across 6 core pillars:
1. **Embedded Sovereign Semantic Memory (`sqlite-vec`)**: In-process vector database in `agent_service/data/memory.db` with zero external database dependencies.
2. **Standardized Tooling (MCP)**: Internal Model Context Protocol servers running inside `agent_service/mcp/` over JSON-RPC.
3. **Glass-Box Tracing & LLMOps (Langfuse)**: Independent Docker monitoring container (`localhost:3100`) capturing thought trees, latency, and costs.
4. **Schema-Strict Self-Correction**: Pydantic tool input/output validation, mid-flight retry, and loop circuit breakers.
5. **Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)**: Standalone `pytest` test harness evaluating agent intelligence without needing Django running.
6. **Sovereign Package Portability**: Fully portable `agent_service/` directory with sanitized export/import CLI pipelines for procedural wisdom.

### 2. Task Milestones & Architectural Alignment
- [x] **Sub-task 0: Architecture Wiki Synchronization (`docs/ai_wiki/`)** - COMPLETED (Commit: `a030672`)
- [x] **Sub-task 1: Clean-Slate Decoupling & Pure Standalone Hermes Provisioning** - COMPLETED (Commit: `f7b11d1`)
- [x] **Sub-task 1.5: Repository Transformation to 100% Standalone AI Agent Platform** - COMPLETED (Backed up full stack to `archive/full-stack-django-frontend`; removed `backend/`, `frontend/`, and `scripts/`; stopped all backend/frontend containers; scrubbed all Django references from `index.md`, `architecture.md`, `agent_team.md`, and `README.md`)
- [ ] **Milestone 1: Embedded Sovereign Memory Engine (`sqlite-vec` in `agent_service/memory/`)** - PENDING
- [ ] **Milestone 2: Standardized FastMCP Server & 5-Profile Refactoring (`agent_service/mcp/`)** - PENDING
- [ ] **Milestone 3: Standalone Langfuse LLMOps Tracing Dashboard in Docker** - PENDING
- [ ] **Milestone 4: Pydantic Schema Contracts & Tiered Risk-Based QA Review** - PENDING
- [ ] **Milestone 5: Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)** - PENDING
- [ ] **Milestone 6: Sovereign Package Portability & Knowledge CLI** - PENDING

### 3. Key Decisions & Deviations (Phase 36)
- *2026-09-13*: User requested comprehensive architecture audit and synchronization before starting code implementation. Updated [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md) (Sections 1, 2, 3, 7, and new Sections 25–31) and [`docs/ai_wiki/index.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/index.md) to fully document the Sovereign Decoupled Architecture, embedded `sqlite-vec` memory engine, FastMCP tool servers, Langfuse :3100 container, 3-tier risk-based QA state machine, golden evals, and cross-project knowledge CLI.
- *2026-09-13*: User instructed that legacy profiles/skills had not performed meaningful work and should not be archived. Wiped `agent_service/` completely to a spotless slate, severed shared filesystem volume mounts in `backend/docker-compose.yml`, and rebooted Hermes as a 100% standalone, decoupled gateway daemon on port 8643 with zero profiles and zero Django dependencies.
- *2026-09-13*: **Total Decoupling & Repository Transformation**: Per user direction ("شيل لي الـ Django خالص من الـ project... حتى ذكره ميكونش موجود ولا في الـ architecture ولا في أي حاجة"), the entire legacy full-stack application was archived to a dedicated Git branch `archive/full-stack-django-frontend`. The `backend/`, `frontend/`, `scripts/`, and `install.sh` folders were removed from the workspace. All backend/frontend Docker containers were stopped and removed. All documentation, architecture specifications, and environment configurations were scrubbed to focus 100% on the **Sovereign Autonomous AI Agent Platform**.

### 4. Current Focus
Repository fully converted to pure Sovereign AI Agent Platform. Ready to begin Milestone 1: Embedded Sovereign Memory Engine (`sqlite-vec` in `agent_service/memory/`).







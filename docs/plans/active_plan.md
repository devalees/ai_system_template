# Implementation Plan: Universal AI System Template & Agent Ecosystem

- **Status**: PENDING <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `main`
- **Last Updated**: 2026-09-09 15:58:00+03:00

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

## Phase 12: Core Foundations, Modular App Settings & Multi-Language Engine (`apps.core`) (PENDING)

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
- [ ] **Sub-task 1: Abstract Base Models (`apps.core.models`) & Request Context Middleware** - PENDING
- [ ] **Sub-task 2: Dynamic Settings Registry, Type Validators & Secret Encryption** - PENDING
- [ ] **Sub-task 3: Database Models (`AppSettingValue`) & Redis Caching Layer** - PENDING
- [ ] **Sub-task 4: Fast Runtime Resolution Service (`get_setting`, `set_setting`) with Code/Env Fallback** - PENDING
- [ ] **Sub-task 5: Unified Odoo-Style Admin Settings Hub with Categorized App Sidebar** - PENDING
- [ ] **Sub-task 6: Bilingual Multi-Language Engine (i18n/l10n, Arabic RTL, LocaleMiddleware & Profile Language)** - PENDING
- [ ] **Sub-task 7: Migrate Existing Hardcoded Constants (Hermes Timeouts, Budget Caps, Defaults) to Settings Registry** - PENDING
- [ ] **Sub-task 8: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 9: LLM Wiki & Architecture Synchronization** - PENDING



---

## Phase 13: Multi-Tenancy, Organizations & Workspaces (`apps.tenants`) (PENDING)

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
- [ ] **Sub-task 1: Organization, Membership & Invitation Data Models** - PENDING
- [ ] **Sub-task 2: Tenant Scoping Middleware & Active Workspace Resolver** - PENDING
- [ ] **Sub-task 3: TenantAwareModel Abstract Base & Filtered Managers** - PENDING
- [ ] **Sub-task 4: Django Admin & DRF ViewSet Scoping Integration** - PENDING
- [ ] **Sub-task 5: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 6: LLM Wiki & Architecture Synchronization** - PENDING

---

## Phase 14: Comprehensive Activity Audit Trail (`apps.audit`) (PENDING)

### 1. Objective & Scope
Build an enterprise-grade, immutable activity audit trail tracking human, bot service account, and system actions for compliance (SOC2, GDPR, ISO 27001):
- **Universal Audit Log (`ActivityLog`)**:
  - Fields: `actor` (User/Bot), `action` (`login`, `logout`, `create`, `update`, `delete`, `export`, `impersonate`), `content_type` & `object_id` (Generic Foreign Key to any record), `changes` (structured JSON diff of old vs new values), `ip_address`, `user_agent`, and `timestamp`.
- **Automatic Lifecycle Auditing**:
  - Model signal receiver automatically calculating attribute diffs for registered auditable models.
  - Security event logging (login failures, password resets, permission changes).

### 2. Task Checklist & Progress
- [ ] **Sub-task 1: ActivityLog Model & Generic Relationship Architecture** - PENDING
- [ ] **Sub-task 2: Automated Signal-Based Model Diffing & Change Tracker** - PENDING
- [ ] **Sub-task 3: Authentication & Security Event Logging Middleware** - PENDING
- [ ] **Sub-task 4: Read-Only Audit Admin Dashboard with JSON Diff Viewer** - PENDING
- [ ] **Sub-task 5: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 6: LLM Wiki & Architecture Synchronization** - PENDING

---

## Phase 15: Universal Notifications Engine (`apps.notifications`) (PENDING)

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
- [ ] **Sub-task 1: Notification & NotificationPreference Data Models** - PENDING
- [ ] **Sub-task 2: Dispatcher Service Layer & Multi-Channel Adapters** - PENDING
- [ ] **Sub-task 3: Celery Asynchronous Email & Webhook Tasks** - PENDING
- [ ] **Sub-task 4: REST API Endpoints (Inbox, Mark-as-Read, Unread Count)** - PENDING
- [ ] **Sub-task 5: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 6: LLM Wiki & Architecture Synchronization** - PENDING

---

## Phase 16: Universal Document & Media Management (`apps.media`) (PENDING)

### 1. Objective & Scope
Unified file, document, and media management handling user uploads, generated agent reports, exports, PDFs, and attachments:
- **Attachment & Document Architecture**:
  - `Document` / `Attachment`: `file`, `filename`, `file_size`, `mime_type`, `uploaded_by`, `organization`, `is_public`, `checksum_sha256` (deduplication and integrity checking).
  - Generic Foreign Key (`content_type`, `object_id`) allowing documents to be attached to any system record (`AgentTask`, `User`, `Organization`, etc.).
- **Storage & Security**:
  - Docker volume local storage with pluggable S3/MinIO cloud storage abstraction.
  - Secure signed download URLs for private documents.

### 2. Task Checklist & Progress
- [ ] **Sub-task 1: Document Data Model with SHA-256 Checksums & Generic FK** - PENDING
- [ ] **Sub-task 2: Pluggable Storage Backend & Secure File Serving Service** - PENDING
- [ ] **Sub-task 3: Generic Attachment Inline for Django Admin** - PENDING
- [ ] **Sub-task 4: REST API Endpoints for File Upload & Retrieval** - PENDING
- [ ] **Sub-task 5: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 6: LLM Wiki & Architecture Synchronization** - PENDING

---

## Phase 17: Developer API Gateway, Scoped Keys & Inbound Webhooks (`apps.api_gateway`) (PENDING)

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
- [ ] **Sub-task 1: APIKey Model, Hashing & DRF Authentication Backend** - PENDING
- [ ] **Sub-task 2: InboundWebhook Model & HMAC Signature Verifier** - PENDING
- [ ] **Sub-task 3: Inbound Webhook Ingestion API & Automation Bridge** - PENDING
- [ ] **Sub-task 4: Django Admin Key Management & Event Inspector** - PENDING
- [ ] **Sub-task 5: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 6: LLM Wiki & Architecture Synchronization** - PENDING

---

## Phase 18: Dynamic Visual Reporting & PDF Generation Engine (`apps.reports`) (PENDING)

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
  - Preview endpoint (`GET /api/reports/templates/<id>/preview/?record_id=...&format=html`) and binary download endpoint (`GET /api/reports/templates/<id>/render/?record_id=...&format=pdf`).
- **Automation & Agent Ecosystem Bridge**:
  - Register `generate_pdf_report` action in `apps.automation` allowing triggers (e.g. Invoice approved, Task completed) to automatically compile reports, attach them to `apps.media`, and dispatch via `apps.notifications`.

### 2. Task Checklist & Progress
- [ ] **Sub-task 1: ReportTemplate & ReportExecutionLog Data Models (`apps.reports.models`)** - PENDING
- [ ] **Sub-task 2: WeasyPrint Engine & CSS Paged Media Service Layer** - PENDING
- [ ] **Sub-task 3: Model Introspection Token Bridge & Template Compiler** - PENDING
- [ ] **Sub-task 4: REST API Endpoints (Template CRUD, Live HTML Preview, PDF Render)** - PENDING
- [ ] **Sub-task 5: Automation Engine Action Registration (`generate_pdf_report`)** - PENDING
- [ ] **Sub-task 6: Django Admin Interface with Live Preview Actions** - PENDING
- [ ] **Sub-task 7: Automated Testing & Verification** - PENDING
- [ ] **Sub-task 8: LLM Wiki & Architecture Synchronization** - PENDING

---

### 4. Current Focus
Awaiting user review and additional feature inputs for Phases 12 through 18 before beginning Phase 12 execution.



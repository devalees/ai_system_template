# Implementation Plan: Universal AI System Template & Agent Ecosystem

- **Status**: COMPLETED <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `feat/agent-rbac-service-accounts`
- **Last Updated**: 2026-09-09 04:15:00+03:00

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
Phase 3 fully complete. Ready to push branch to remote repository.



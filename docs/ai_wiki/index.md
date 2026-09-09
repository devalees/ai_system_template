# AI System Template — System Overview

An extensible, production-grade starter template pairing a **Django** web framework (REST API, Admin, PostgreSQL, Redis) with the autonomous **Nous Research Hermes Agent** execution runtime in Docker, featuring isolated specialist agent profiles, custom skill auditing, and dynamic model catalogs.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `feat/unified-user-profile-architecture`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Status**: Phase 4 Completed (Unified Django User-Profile Architecture & Live Hermes Profile Selector)

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



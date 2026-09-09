# AI System Template — System Overview

An extensible, production-grade starter template pairing a **Django** web framework (REST API, Admin, PostgreSQL, Redis) with the autonomous **Nous Research Hermes Agent** execution runtime in Docker, featuring isolated specialist agent profiles, custom skill auditing, and dynamic model catalogs.

- **Repository**: `devalees/ai_system_template`
- **Active Branch**: `feat/core-agent-profiles`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Architecture Reference**: [`docs/ai_wiki/architecture.md`](file:///home/ehab/Desktop/economy_editor/docs/ai_wiki/architecture.md)
- **Status**: Phase 2 Completed (Core Agent Profiles & Model Catalog Integration)

---

## Primary System Components

### 1. Backend Service (`backend/`)
- **Framework**: Django 5.x with Django REST Framework on Python 3.11.
- **Data Persistence**: PostgreSQL 16 relational database with Redis 7 caching and session broker.
- **Dynamic Administrative Portal**: Django Admin with dynamic, dependent `<select>` dropdowns for provider and model selection.
- **Model Catalog Engine**: Powered by `models.dev` dynamic registry and OpenRouter, rendering live context window length and token pricing cards ($/1M tokens).
- **Core Models**:
  - `AgentProfile`: Profile registry matching Hermes profiles with providers, model overrides, and reasoning effort levels (`none`, `low`, `medium`, `high`, `max`).
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
- **Review Pipeline**: Tasks transition across `pending` → `in_progress` → `review` → `completed` / `failed`, reviewed by `qa_auditor` via `POST /api/tasks/<id>/submit_verdict/`.

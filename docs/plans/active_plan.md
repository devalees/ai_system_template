# Implementation Plan: Universal AI System Template & Agent Ecosystem

- **Status**: IN_PROGRESS <!-- PENDING | IN_PROGRESS | COMPLETED -->
- **Active Branch**: `feat/core-agent-profiles`
- **Last Updated**: 2026-09-08 16:38:00+03:00

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

## Phase 2: 5 Universal Core Agent Profiles (IN_PROGRESS)

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
- [x] **Sub-task 4: Foundation Skills for Specialist Profiles (`agent_service/skills/`)** - COMPLETED (Pending user commit approval)
- [ ] **Sub-task 5: Django Backend Profile Integration & Task Registry (`backend/apps/integration/`)** - PENDING
- [ ] **Sub-task 6: End-to-End Verification & Documentation Synchronization** - PENDING

### 3. Key Decisions & Deviations (Phase 2)
- *2026-09-08*: Created branch `feat/core-agent-profiles`.
- *2026-09-08*: Profiles defined declaratively in `agent_service/profiles/<name>/` with dedicated `SOUL.md`, `config.yaml`, and `profile.yaml` for each of the 5 roles (`orchestrator`, `cost_controller`, `qa_auditor`, `comms_agent`, `archivist`).
- *2026-09-08*: Formally clarified in global workflow rules that `active_plan.md` is cumulative and append-only across all project phases.
- *2026-09-08*: Committed and pushed Sub-task 2 (Commit: `0d219b6`).
- *2026-09-08*: Implemented `scripts/provision_profiles.py` with cross-environment execution support (host & container), successfully provisioned all 5 profiles into Hermes runtime, and empirically verified persona inference on OpenRouter with `google/gemini-2.5-flash` (Commit: `1f09b23`).
- *2026-09-08*: Built and verified specialist foundation skills: `cost_monitor` (real-time token accounting & budget status across all profile SQLite databases) and `output_validator` (empirical syntax, hygiene, and security audit for the QA review gate).

### 4. Current Focus
Awaiting user review and commit approval for Sub-task 4, then proceeding to Sub-task 5 (Django Backend Profile Integration).

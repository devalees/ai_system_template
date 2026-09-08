# System Architecture: Decoupled AI System Template

## 1. Technical Stack & Security Isolation

- **Backend Web Framework**: Django 5.x + Django REST Framework (Python 3.11)
- **Agent Engine**: Hermes Agent (`hermes-agent:local` / Nous Research)
- **Database**: PostgreSQL 16
- **Cache & Broker**: Redis 7
- **Container Architecture**: **Two Isolated Docker Projects**
  1. `backend/docker-compose.yml`: Encapsulates Django, PostgreSQL, and Redis in an internal network (`backend_network`).
  2. `agent_service/docker-compose.yml`: Encapsulates Hermes Agent in an isolated network (`hermes_isolated_network`).
- **Inter-Service Communication**: Strictly over HTTP REST API (`http://host.docker.internal:8000/api`) with zero shared container networks, storage, or privileges.

---

## 2. Port Allocation

| Service | Environment | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| `backend` | Django Project | 8000 | 8000 | Django REST API & Admin Portal |
| `db` | Django Project | 5432 | 5432 | PostgreSQL 16 Relational Store |
| `redis` | Django Project | 6379 | 6379 | Redis 7 Cache & Message Broker |
| `hermes` | Hermes Project | 8643 | 8642 | Hermes Agent Gateway daemon |

---

## 3. Directory Layout

```
economy_editor/
├── agent_service/                   # Hermes Agent Container & Profiles
│   ├── docker-compose.yml           # Hermes isolated container definition
│   ├── profiles/                    # Declarative profile configurations
│   │   ├── orchestrator/            # Chief of Staff (intake & triage)
│   │   ├── cost_controller/         # Financial & spend auditor
│   │   ├── qa_auditor/              # Quality assurance gatekeeper
│   │   ├── comms_agent/             # Client communications & intake
│   │   └── archivist/               # Documentation & institutional memory
│   └── skills/                      # Custom specialist skills
│       ├── cost_monitor/            # SQLite token & spend aggregation
│       └── output_validator/        # AST syntax & leak validation
├── backend/                         # Django Web Service
│   ├── apps/
│   │   └── integration/             # Integration App
│   │       ├── admin.py             # Admin UI with custom media JS
│   │       ├── forms.py             # Dependent select forms
│   │       ├── models.py            # AgentProfile, AgentTask, SpendReport
│   │       ├── services/
│   │       │   └── hermes_catalog.py # models.dev dynamic registry client
│   │       ├── static/admin/js/     # Dynamic dependent dropdowns & specs card
│   │       └── views.py             # REST API endpoints & catalog views
│   └── docker-compose.yml           # Django, DB, and Redis stack
├── docs/
│   ├── ai_wiki/                     # System architecture & documentation wiki
│   │   ├── index.md                 # System overview & components
│   │   └── architecture.md          # Detailed architectural patterns
│   └── plans/
│       └── active_plan.md           # Cumulative, append-only task plan
└── scripts/
    └── provision_profiles.py        # Automated profile provisioning script
```

---

## 4. Data Models (`backend/apps/integration/models.py`)

### `AgentProfile`
- `name`: Unique slug (`orchestrator`, `cost_controller`, `qa_auditor`, `comms_agent`, `archivist`).
- `display_name`: Human-readable title (e.g. "Chief of Staff / Orchestrator").
- `role`: Canonical role choice.
- `provider`: Inference provider slug (`openrouter`, `anthropic`, `openai-api`, `gemini`, `deepseek`, etc.).
- `model_name`: Selected model identifier (e.g. `google/gemini-2.5-flash`, `claude-sonnet-4-6`).
- `is_active`: Boolean flag controlling execution eligibility.
- `description`: Role narrative and assignment boundaries.

### `AgentTask`
- `task_name`: Human-readable task title.
- `assigned_profile`: Foreign key to `AgentProfile`.
- `status`: Workflow state (`pending`, `in_progress`, `review`, `completed`, `failed`).
- `review_verdict`: QA decision (`pending`, `approved`, `rejected`, `changes_requested`).
- `cost_usd`: Measured token cost incurred during execution.
- `reviewer_notes`: Structured feedback from `qa_auditor`.

### `SpendReport`
- `reported_by`: Profile identifier (typically `cost_controller`).
- `total_cost_usd`: Aggregated expenditure.
- `daily_budget_usd`: Configured ceiling.
- `budget_status`: `OK`, `WARNING`, or `EXCEEDED`.
- `total_tokens`: Token volume tracked across sessions.
- `total_api_calls`: Total LLM invocations.

---

## 5. Hermes Multi-Profile Architecture

- **Isolation**: Each profile maintains an isolated directory under `/root/.hermes/profiles/<name>/` with its own `config.yaml`, `SOUL.md`, `.env`, and SQLite `state.db`.
- **Invocation**: Agents are executed directly using the profile flag:
  ```bash
  hermes -p <profile_name> -z "Task prompt"
  ```
- **Declarative Source of Truth**: Source definitions reside in `agent_service/profiles/` and are synchronized via `scripts/provision_profiles.py`.

---

## 6. Dynamic Model Catalog Engine (`models.dev`)

- **Live Registry**: Integrates `models.dev/api.json` — the same universal registry powering Hermes Agent CLI — with automatic in-memory and disk caching (`/tmp/models_dev_cache.json`, 4-hour TTL).
- **Noise Suppression**: Applies Hermes' native regex filters (`_NOISE_PATTERNS`, `_GOOGLE_HIDDEN_MODELS`) to eliminate audio, TTS, embeddings, and deprecated models.
- **Dynamic Admin Form**: In Django Admin, selecting a `provider` triggers an asynchronous client fetch to `/api/hermes/models/?provider=<slug>`, populating modern models and rendering a live **Model Specifications & Pricing Card** displaying:
  - Context Window length (e.g. 1,000,000 tokens)
  - Input Token Cost ($ / 1M tokens)
  - Output Token Cost ($ / 1M tokens)
  - Modalities and reasoning capabilities

---

## 7. Quality Assurance & Review State Machine

```
[AgentTask: Pending]
        │
        ▼
[AgentTask: In Progress] (Assigned Agent executes task)
        │
        ▼
[AgentTask: Review] ────► [QA Auditor checks deliverable via output_validator]
                                │
        ┌───────────────────────┴────────────────────────┐
        ▼                                                ▼
[Approved]                                     [Changes Requested / Rejected]
        │                                                │
        ▼                                                ▼
[Status: Completed]                            [Status: In Progress / Failed]
```

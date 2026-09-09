# System Architecture: Decoupled AI System Template

## 1. Technical Stack & Security Isolation

- **Backend Web Framework**: Django 5.x + Django REST Framework (Python 3.11)
- **Agent Engine**: Hermes Agent (`hermes-agent:local` / Nous Research)
- **Database**: PostgreSQL 16
- **Cache & Broker**: Redis 7
- **Container Architecture**: **Two Isolated Docker Projects**
  1. `backend/docker-compose.yml`: Encapsulates Django, Celery Worker, Celery Beat, PostgreSQL, and Redis in an internal network (`backend_network`).
  2. `agent_service/docker-compose.yml`: Encapsulates Hermes Agent in an isolated network (`hermes_isolated_network`).
- **Inter-Service Communication**: Strictly over HTTP REST API (`http://host.docker.internal:8000/api`) with zero shared container networks, storage, or privileges.

---

## 2. Port Allocation & Containers

| Service | Container Name | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| `backend` | `django-template-backend` | 8000 | 8000 | Django REST API & Admin Portal |
| `celery_worker` | `django-template-celery-worker` | - | - | Celery Distributed Task Worker |
| `celery_beat` | `django-template-celery-beat` | - | - | Celery Beat Database Scheduler |
| `db` | `django-template-db` | 5432 | 5432 | PostgreSQL 16 Relational Store |
| `redis` | `django-template-redis` | 6379 | 6379 | Redis 7 Cache & Celery Broker |
| `hermes` | `hermes-template-agent` | 8643 | 8642 | Hermes Agent Gateway daemon |

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
│   │   ├── automation/              # Centralized Automation Engine & Service Registry
│   │   │   ├── actions.py           # Registered action handlers (Hermes, webhook, script, internal)
│   │   │   ├── admin.py             # Automation Admin with live toggles & Run Now action
│   │   │   ├── engine.py            # Event dispatcher, condition evaluator & Celery worker bridge
│   │   │   ├── forms.py             # Dynamic App/Model discovery & JSON Schema payload forms
│   │   │   ├── models.py            # AutomationRule & AutomationLog
│   │   │   ├── registry.py          # 4-category ServiceRegistry with dynamic introspection
│   │   │   ├── scheduler.py         # django-celery-beat synchronization engine
│   │   │   ├── tasks.py             # Celery asynchronous execution tasks
│   │   │   └── views.py             # REST API endpoints (/api/automation/)
│   │   └── integration/             # Integration App
│   │       ├── admin.py             # Admin UI with custom media JS
│   │       ├── forms.py             # Dependent select forms
│   │       ├── models.py            # AgentProfile, AgentTask, SpendReport
│   │       ├── services/
│   │       │   └── hermes_catalog.py # models.dev dynamic registry client
│   │       ├── static/admin/js/     # Dynamic dependent dropdowns & specs card
│   │       └── views.py             # REST API endpoints & catalog views
│   ├── core/                        # Django Project Configuration & Celery Setup
│   │   ├── celery.py                # Celery application initialization
│   │   └── settings.py              # Celery & django-celery-beat broker settings
│   └── docker-compose.yml           # Django, Celery Worker, Celery Beat, DB, and Redis stack
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

### `Profile` (Aliased as `AgentProfile`)
- `user`: OneToOneField to `auth.User` via automatic `post_save` lifecycle signals.
- `is_agent`: Boolean flag indicating whether account acts as an autonomous AI agent.
- `user_type`: Choice field (`human`, `agent`, `client`) for clear multi-user categorization.
- `hermes_profile_name`: Hermes runtime folder/profile slug (`orchestrator`, `cost_controller`, etc.).
- `name`: Profile identifier / alias (backward compatible).
- `display_name`: Human-readable title (e.g. "Chief of Staff / Orchestrator").
- `role`: Canonical role choice (`orchestrator`, `finance`, `quality_assurance`, `communications`, `knowledge_management`, `general`).
- `provider`: Inference provider slug (`openrouter`, `anthropic`, `openai-api`, `gemini`, `deepseek`, etc.).
- `model_name`: Selected model identifier (e.g. `google/gemini-2.5-flash`, `claude-sonnet-4-6`).
- `reasoning_effort`: Thinking/reasoning token budget (`none`, `low`, `medium`, `high`, `max`).
- `is_active`: Boolean flag controlling execution eligibility.
- `description`: Role narrative and assignment boundaries.

### `AgentTask`
- `created_by`: ForeignKey to `auth.User` tracking dispatching agent / service account.
- `task_name`: Human-readable task title.
- `assigned_profile`: Foreign key to `AgentProfile`.
- `status`: Workflow state (`pending`, `in_progress`, `review`, `completed`, `failed`).
- `review_verdict`: QA decision (`pending`, `approved`, `rejected`, `changes_requested`).
- `reasoning_effort`: Task-specific override (`inherit`, `none`, `low`, `medium`, `high`, `max`).
- `cost_usd`: Measured token cost incurred during execution.
- `reviewer_notes`: Structured feedback from `qa_auditor`.

### `SpendReport`
- `created_by`: ForeignKey to `auth.User` (must be `bot_cost_controller`).
- `reported_by`: Profile identifier (typically `cost_controller`).
- `total_cost_usd`: Aggregated expenditure.
- `daily_budget_usd`: Configured ceiling.
- `budget_status`: `OK`, `WARNING`, or `EXCEEDED`.
- `total_tokens`: Token volume tracked across sessions.
- `total_api_calls`: Total LLM invocations.

---

## 5. Hermes Multi-Profile Architecture & Reasoning Ladder

- **Isolation**: Each profile maintains an isolated directory under `/root/.hermes/profiles/<name>/` with its own `config.yaml`, `SOUL.md`, `.env`, and SQLite `state.db`.
- **Reasoning Effort Ladder**: Profiles configure native `agent.reasoning_effort` (`none`, `low`, `medium`, `high`, `max`). Hermes Agent automatically enforces wire clamping (`clamp_effort`) so unsupported vendor levels degrade gracefully to the nearest supported level without throwing errors.
- **Invocation**: Agents are executed directly using profile and reasoning flags:
  ```bash
  hermes -p <profile_name> --reasoning <level> -z "Task prompt"
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

---

## 8. Role-Based Access Control (RBAC) & Service Account Architecture

To uphold the Principle of Least Privilege across the multi-agent ecosystem, agent profiles do not share a single master API key or operate with unbounded administrative access. Instead, each profile operates as an isolated Django Service Account bound to native Django permissions.

### 8.1 Service Account & Permission Matrix

| Profile | Bot User (`auth.User`) | Django Group (`auth.Group`) | Model Permissions (`auth.Permission`) | Endpoint Access |
| :--- | :--- | :--- | :--- | :--- |
| `orchestrator` | `bot_orchestrator` | `Agent_Orchestrator` | `view_agentprofile`, `view_agenttask`, `add_agenttask`, `change_agenttask` | POST/GET `/api/tasks/`, GET `/api/profiles/` |
| `cost_controller` | `bot_cost_controller` | `Agent_CostController` | `view_spendreport`, `add_spendreport`, `view_agentprofile` | POST/GET `/api/spend-reports/`, GET `/api/profiles/` |
| `qa_auditor` | `bot_qa_auditor` | `Agent_QAAuditor` | `view_agenttask`, `change_agenttask`, `view_agentprofile` | GET `/api/tasks/`, POST `/api/tasks/<id>/submit-verdict/` |
| `comms_agent` | `bot_comms_agent` | `Agent_CommsAgent` | `view_agenttask`, `view_agentprofile` | GET `/api/tasks/`, GET `/api/profiles/` |
| `archivist` | `bot_archivist` | `Agent_Archivist` | `view_agentprofile`, `view_agenttask` | GET `/api/profiles/`, GET `/api/tasks/` |

### 8.2 Endpoint Authorization & Defense-in-Depth

- **`StrictDjangoModelPermissions`**: Custom DRF permission class mapping HTTP verbs to native Django permissions:
  - `GET`, `HEAD` -> `view_<model>`
  - `POST` -> `add_<model>`
  - `PUT`, `PATCH` -> `change_<model>`
  - `DELETE` -> `delete_<model>`
- **Cost Controller Boundary**: `bot_cost_controller` possesses `add_spendreport` but lacks `add_agenttask`. Any attempt by `cost_controller` to POST to `/api/tasks/` is immediately rejected with `403 Forbidden`.
- **Review Gate Defense**: `AgentTaskViewSet.submit_verdict` explicitly validates that the authenticated caller belongs to `Agent_QAAuditor` and holds `change_agenttask` permission. Submitting reviews from unauthorized profiles (such as `cost_controller` or `orchestrator`) is strictly blocked (`403 Forbidden`).
- **Audit Trails**: `AgentTask` and `SpendReport` models capture `created_by`, automatically populated from `request.user` via DRF `perform_create()`.

### 8.3 Runtime Token Provisioning Flow

```
[Django: seed_profiles]
       │
       ▼ (Generates bot users, groups, permissions & DRF tokens)
[/tmp/agent_tokens.json]
       │
       ▼ (scripts/provision_profiles.py reads manifest)
[/root/.hermes/profiles/<profile_name>/.env] (Injected inside Hermes container)
       │
       ▼
[Hermes Runtime: DJANGO_API_TOKEN] (Sourced on profile execution: hermes -p <profile>)
```

---

## 9. Unified User-Profile Architecture & Live Hermes Engine Discovery

### 9.1 Idiomatic 1-to-1 User Profile Lifecycle
Rather than treating AI agents as an isolated, detached entity, the system follows standard Django best practices:
- **`auth.User` as Universal Identity**: Every actor—human administrator, client, or autonomous AI agent—is represented by a standard Django `User`.
- **Automatic Lifecycle Signal**: A `post_save` receiver on `User` automatically provisions or retrieves a linked `Profile` record (`user.profile`), eliminating orphaned records.
- **Categorization Flags**:
  - `is_agent`: Determines if the account executes LLM agent tasks.
  - `user_type`: `human` (staff/internal), `agent` (bot worker), or `client` (external user).

### 9.2 Live Hermes Profile Discovery
- **Direct Engine Visibility**: The declarative profile definitions directory (`agent_service/profiles/`) is mounted read-only into `/app/agent_profiles/` inside the Django backend container.
- **Service Layer (`HermesDiscoveryService`)**: Inspects runtime folders, dynamically parses `profile.yaml` and `config.yaml`, and returns structured metadata (display name, canonical role, default model).
- **REST Discovery API**: `GET /api/hermes/profiles/` exposes available profiles live to client interfaces and Django Admin.

### 9.3 Single-Screen Admin UI & 🔄 Reload Widget
- **`CustomUserAdmin`**: Unregisters Django's default User admin to embed `ProfileInline` directly in the user edit page.
- **Interactive Selector**: The `hermes_profile_name` input is rendered as a `<select>` dropdown accompanied by an AJAX **🔄 Reload Profiles** button (`hermes_profile_selector.js`).
- **Dynamic Pre-fill**: Selecting an engine profile automatically pre-populates display name, canonical role, and default inference model while keeping `is_agent=True`.

---

## 10. Centralized Automation Engine & Service Registry Architecture (`apps.automation`)

### 10.1 Service Registry & Action Registration
The automation framework decouples trigger detection from business execution via a centralized, in-memory `ServiceRegistry` instance (`automation_registry`):
- **4 Categorized Service Types**:
  - `hermes_agent`: Actions invoking Hermes Agent profiles or dispatching agent tasks.
  - `internal_app`: Core domain actions (e.g. Django model updates, state synchronization).
  - `script_service`: Custom local utility scripts and routines.
  - `external_webhook`: Outbound HTTP webhook dispatches with customizable headers and payload mapping.
- **Decorator-Based Registration**: Action handlers are registered cleanly via `@register_action`:
  ```python
  @register_action(
      action_id="auto_provision_hermes_profile",
      name="Auto-Provision Hermes Profile",
      category="hermes_agent",
      description="Generates bot user, DRF token, declarative files, and runtime .env",
      payload_schema={...}
  )
  def auto_provision_hermes_profile(payload, context): ...
  ```
- **Dynamic Introspection**: Zero-touch model discovery utilizes `django.apps.apps.get_models()`. Form choices dynamically present all installed models formatted as `<app_label>.<ModelName>` and expose field dictionaries for target conditions.

### 10.2 Triggers: Model Events, State Transitions & Time Schedules
Each `AutomationRule` (exposed in Admin as **Automation Action**) is bound to either a `model_event` or `time_based` trigger:
1. **Model Event & State Transition Triggers (Odoo-Style)**:
   - Supported actions: `created` (post_save created=True), `updated` (post_save created=False), `field_changed` (state transitions), `deleted` (post_delete), or `any`.
   - **State Transition Engine**: Employs a lightweight `pre_save` signal hook caching the database state (`_automation_old_values`). On `post_save`, `AutomationEngine` computes `changed_fields` and evaluates:
     - `trigger_field`: Monitors a specific attribute (e.g. `status` or `review_verdict`).
     - `previous_value`: Ensures the field transitioned *from* this value (e.g. `review`).
     - `target_value`: Ensures the field transitioned *to* this value (e.g. `completed`).
   - Dynamic lifecycle signals inspect `filter_conditions` (e.g. `{"is_agent": True}`).
   - Safe signal connection: Core model signals are connected on module import, while dynamic models declared in active rules are connected post-migration and during rule save.
2. **Time-Based Triggers**:
   - **Mode: `once`**: One-shot trigger scheduled at a fixed `run_at` ISO datetime. Once fired, the rule automatically transitions `is_active=False`.
   - **Mode: `recurring`**: Recurring interval or cron-based execution.
   - **Supported Units**: `seconds`, `minutes`, `hours`, `days`, `weeks`, `months`.
   - Native integration with `django_celery_beat.models.PeriodicTask`, `IntervalSchedule`, and `CrontabSchedule`.
   - **Admin Cleanliness**: Raw Celery Beat tables (`ClockedSchedule`, `CrontabSchedule`, `IntervalSchedule`, `SolarSchedule`, `PeriodicTask`) are unregistered from Django Admin, presenting a clean interface centered exclusively on **Automation Actions** and **Automation Logs**.

### 10.3 Celery & Celery Beat Execution Flow
```
[Event / Beat Clock]
         │
         ▼
[AutomationEngine.evaluate_and_trigger()] 
         │ (Applies filter_conditions & creates AutomationLog: pending)
         ▼
[Celery Task: run_automation_rule.delay(rule_id, context, log_id)]
         │
         ▼
[Celery Worker: executes action handler]
         │
         ├─► [SUCCESS] ──► AutomationLog: status='success', output_data={...}
         └─► [FAILURE] ──► AutomationLog: status='failed', error_message='...'
```

### 10.4 Flagship Action: Dynamic Hermes Profile Auto-Provisioning
When an administrative user or API client creates an AI Agent account (`Profile.is_agent=True`):
1. **Trigger**: Model event post-save on `integration.Profile` fires matching rule.
2. **Execution**: Celery worker runs `auto_provision_hermes_profile`:
   - Ensures an associated `auth.User` and DRF `Token` exist.
   - Generates declarative profile files in `/app/agent_profiles/<profile_name>/`:
     - `SOUL.md`: Role-specific system instructions.
     - `config.yaml`: LLM provider, default model, and reasoning parameters.
     - `profile.yaml`: Metadata manifest.
   - Generates runtime environment file `/app/hermes_runtime_profiles/<profile_name>/.env` injecting:
     - `DJANGO_API_TOKEN`
     - `HERMES_PROFILE`
     - `MODEL_NAME`
     - Provider API keys.
3. **Immediate Availability**: Hermes Agent detects the profile directory immediately without requiring container restarts.

### 10.5 JSON Serialization & Resilient Architecture
- **UUID & Datetime Handling**: To prevent database JSONField serialization errors (`TypeError: Object of type UUID is not JSON serializable`), `AutomationEngine` recursively transforms all inputs via `make_json_serializable()`.
- **Decoupled Bootstrapping**: `AppConfig.ready()` bypasses database queries during initialization, ensuring zero `RuntimeWarning` or migration deadlocks on greenfield database setup.




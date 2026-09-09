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
│   │   ├── core/                    # Core foundations, base models, settings hub & i18n
│   │   ├── integration/             # Integration App & Hermes catalog
│   │   └── meta_engine/             # Metadata Engine & Modular App Runtime
│   │       ├── admin.py             # Admin App Store & Studio UI
│   │       ├── app_installer.py     # Multi-pass declarative app installer
│   │       ├── app_uninstaller.py   # Reverse dependency guard & safe uninstaller
│   │       ├── dependency_resolver.py # DAG topological dependency sorter
│   │       ├── manifest_reader.py   # Package scanner and manifest parser
│   │       ├── model_factory.py     # Dynamic in-memory model compiler
│   │       ├── models.py            # SystemModule & Meta catalog models
│   │       ├── schema_engine.py     # Dynamic PostgreSQL DDL engine
│   │       ├── serializers.py       # Dynamic DRF entity serializer factory
│   │       ├── signals.py           # Database DDL synchronization signals
│   │       ├── urls.py              # Entity gateway & App Store routes
│   │       └── views.py             # Polymorphic CRUD & schema endpoints
│   ├── modules/                     # Modular Application Packages
│   │   ├── contacts/                # Reference Contacts & Address Book app
│   │   └── crm/                     # Reference CRM & Sales Pipeline app
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

### 10.6 Next-Gen Odoo-Style Automation Actions (Phase 6)
- **Semantic Separation of Source vs. Destination**:
  - `trigger_model`: Source model monitored for database lifecycle triggers (`auth.User`, `integration.Profile`, `integration.AgentTask`).
  - `target_model`: Destination model receiving automated record CRUD operations.
- **Direct Target Model CRUD Operations**:
  - `create`: Instantiates new records on `target_model` with mapped fields and type coercion.
  - `update`: Locates records via `target_record_id`, `id`, `pk`, or context `pk`, updating attributes while protecting immutable fields.
  - `delete`: Removes records identified by ID with transactional safety.
- **Dynamic Field Mapping & Template Interpolation**:
  - Declarative `field_mappings` support scalar constants and context interpolation (`{{username}}`, `{{pk}}`, `{{status}}`).
  - Automatic relationship resolution: Foreign key fields automatically resolve username strings, scalar IDs, and related model instances.
- **Visual Condition Rules Engine**:
  - `condition_rules`: Evaluates structured operator rules (`==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `in`, `is_empty`, `is_not_empty`) with dot-notation lookup (`profile.is_agent`).
- **Dynamic Model & Field Introspection API**:
  - `GET /api/automation/introspection/?model=<app_label.ModelName>` provides real-time schema specifications, field types, requirement constraints (`required_fields`), and choice options.
  - Parameterless requests return a complete catalog of all installed system models grouped by Django application.
- **System Signal Reification & Deletion Protection**:
  - Core automation routines (`Auto-Provision Hermes Profile`, `Daily Spend Audit`, `QA Review Routing`, `Daily Budget Alert`) are marked `is_system=True`.
  - Enforces deletion locks across `AutomationRule.delete()` (raising `ValidationError`) and Django Admin (`has_delete_permission`, `delete_queryset`), preventing accidental removal of foundational workflows.
- **Reactive Dynamic Admin UI**:
  - Static script `automation_reactive_admin.js` provides conditional fieldset toggles (showing/hiding Model Event vs. Beat Scheduling sections), live AJAX schema introspection, and interactive field mapping pills with required field badges.

---

## 11. Decoupled Triggers & 1-to-N Action Pipelines (Phase 7)

```
                       ┌─────────────────────────┐
                       │    AutomationTrigger    │
                       │ (WHEN & Under What Cond)│
                       └────────────┬────────────┘
                                    │ 1-to-N
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │AutomationAction │    │AutomationAction │    │AutomationAction │
    │ [Sequence: 10]  │    │ [Sequence: 20]  │    │ [Sequence: 30]  │
    └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
             │                      │                      │
             ▼                      ▼                      ▼
  [Celery Task Dispatch] [Celery Task Dispatch] [Celery Task Dispatch]
             │                      │                      │
             ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │  AutomationLog  │    │  AutomationLog  │    │  AutomationLog  │
    │ (trigger,action)│    │ (trigger,action)│    │ (trigger,action)│
    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 11.1 Decomposed Data Models
- **`AutomationTrigger` ("WHEN")**: Defines root event sources, lifecycle rules, schedules, and filtering:
  - `trigger_type`: `model_event`, `time_based`, `webhook`, `manual`.
  - `trigger_model`, `event_type`, `filter_conditions`, `condition_rules`.
  - State transitions: `trigger_field`, `previous_value`, `target_value`.
  - Scheduling: `schedule_unit`, `schedule_value`, `scheduled_time`, `periodic_task`.
  - Metrics: `last_triggered_at`, `trigger_count`.
- **`AutomationAction` ("WHAT")**: Represents sequenced, executable steps linked 1-to-N to a parent trigger:
  - `trigger`: ForeignKey to `AutomationTrigger` (`related_name='actions'`).
  - `sequence`: Integer execution ordering (`10, 20, 30...`).
  - Target model operations: `target_model`, `target_operation`, `field_mappings`.
  - Service handlers: `action_category`, `action_type`, `action_params`.
  - Metrics: `last_run_at`, `run_count`.
- **`AutomationLog`**: Audit record retaining foreign keys to both `trigger` and `action`, capturing granular duration, status, context snapshots, output payloads, and stack traces.

### 11.2 Unified Asynchronous Celery Execution
- All automated actions execute asynchronously via Celery distributed workers (`execute_automation_action_task.delay(action.id, context, trigger_source)`).
- Eliminates synchronous execution blockages on web server worker threads, ensuring sub-millisecond HTTP response cycles, Redis task queueing, and uniform observability.
- Celery Beat schedules trigger `scheduled_automation_task`, which automatically evaluates the trigger and enqueues all active actions in sequential order.

### 11.3 Universal System Signal Reification
- **Reified User Profile Lifecycle**: `auth.User` creation is elevated into a first-class automation pipeline (`Auto-Provision Profile on User Creation` trigger + `Provision Django User Profile` action handler).
- Eliminates unobserved hidden side effects and brings core Django framework lifecycle events under the centralized visibility and audit tracking of `AutomationLog`.

### 11.4 Reactive Multi-Action Admin UI
- `AutomationTriggerAdmin` embeds `AutomationActionInline` (with dynamic model and action introspection) and `AutomationLogInline`.
- Allows operators to configure root triggers and view/edit multi-step action sequences and recent execution audit logs on a single unified screen.
- Enhanced with `automation_reactive_admin.js` for instant schema introspection pills and visual condition presets.

---

## 12. Interactive Condition Rules Table Builder & Temporal Engine (Phase 8)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎯 Visual Condition Rules (Trigger Filters)                                            │
├──────────────────────────┬──────────────────────────┬──────────────────────┬───────────┤
│ Field (Model-Aware)      │ Operator                 │ Expected Value       │ Actions   │
├──────────────────────────┼──────────────────────────┼──────────────────────┼───────────┤
│ [ due_date (Date)      ▼]│ [ > (Greater / After)  ▼]│ [ 2026-09-09       ] │ [ ✕ Del ] │
│ [ status (Status)      ▼]│ [ == (Equals)          ▼]│ [ completed        ] │ [ ✕ Del ] │
│ [ notes (Notes)        ▼]│ [ is_empty (Is Null)   ▼]│ [ (disabled)       ] │ [ ✕ Del ] │
├──────────────────────────┴──────────────────────────┴──────────────────────┴───────────┤
│ [ + Add Condition ]  [ 🗑️ Clear All ]                                                  │
│ 💡 Value Formatting & Database Type Guide:                                             │
│ 📅 Dates (Django Standard): YYYY-MM-DD (e.g. 2026-09-09)                                │
│ ⏱️ Timestamps: YYYY-MM-DD HH:MM:SS                                                     │
│ 🔢 Numbers: 10, 3.75, -5.0 | 🔤 Booleans: true / false                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 12.1 Interactive Table Widget in Django Admin
- Replaces raw JSON editing in `condition_rules` with a responsive spreadsheet-like table.
- Dynamically discovers all fields from the selected `trigger_model` via the Introspection API (`/api/automation/introspection/?model=...`).
- Supported Operators: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `not_contains`, `in`, `not_in`, `is_empty`, `is_not_empty`.
- Adapts value input dynamically: disables for null checks, provides type badges, and renders date format reminders.
- Implements continuous two-way synchronization with the underlying Django `JSONField`.

### 12.2 Date Formatting Standard & Engine Temporal Parsing
- Standardizes date values on the Django / PostgreSQL ISO 8601 standard: `YYYY-MM-DD` (Year-Month-Day).
- In `AutomationEngine.evaluate_single_condition`, temporal values (`date`, `datetime`, and ISO strings) are parsed via `try_parse_temporal()`.
- Supports chronological comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`) directly comparing date and datetime components without failing numeric conversions or relying on lexicographical strings.

---

## 13. Unified Filter Conditions Engine with Boolean Logic (AND/OR) & Visual Group Builder (Phase 9)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎯 Trigger Filter Conditions (Boolean Rules with AND, OR & Groups)        [🗑️ Reset All]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [Match for Trigger: ALL of the following (AND) ▼]                                      │
│   ├── [ cost_usd (Decimal) ▼] [ > (Greater Than) ▼] [ 10.0            ] [ ✕ ]          │
│   │                                                                                    │
│   └── ┌── [Match: ANY of the following (OR) ▼] ── Sub-Group ( ... )   [✕ Delete Group] │
│       ├── [ status (Choice)   ▼] [ == (Equals)     ▼] [ review        ] [ ✕ ]          │
│       ├── [ status (Choice)   ▼] [ == (Equals)     ▼] [ urgent        ] [ ✕ ]          │
│       └── [ + Add Condition ]  [ + Add Group (...) ]                                   │
│                                                                                        │
│   [ + Add Condition ]  [ + Add Group (...) ]                                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 💡 Value Formatting & Database Type Guide:                                             │
│ 📅 Dates (Django Standard): YYYY-MM-DD (e.g. 2026-09-09)                                │
│ ⏱️ Timestamps: YYYY-MM-DD HH:MM:SS                                                     │
│ 🔢 Numbers: 10, 3.75, -5.0 | 🔤 Booleans: true / false                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 13.1 Boolean Algebra & Recursive Evaluation Tree
The filtering engine unifies trigger condition evaluation into a single authoritative recursive Boolean algebra structure:
- **Recursive Boolean Specification**:
  ```json
  {
    "combinator": "AND",
    "rules": [
      {"field": "cost_usd", "operator": ">", "value": 10.0},
      {
        "combinator": "OR",
        "rules": [
          {"field": "status", "operator": "==", "value": "review"},
          {"field": "status", "operator": "==", "value": "urgent"}
        ]
      }
    ]
  }
  ```
- **Evaluation Semantics (`AutomationEngine.evaluate_filter_tree`)**:
  - `AND`: Short-circuits on the first rule/group returning `False`.
  - `OR`: Short-circuits on the first rule/group returning `True`.
  - Leaf Rules: Evaluated via `evaluate_single_condition()`, supporting dot-notation nested attributes (`profile.is_agent`), operators (`==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `not_contains`, `in`, `not_in`, `is_empty`, `is_not_empty`), and temporal ISO date comparison.
- **In-Flight vs. Database Query Lifecycle**:
  - **Database Model Events (`model_event: created, updated, deleted`)**: The filter runs in-memory against the in-flight snapshot context captured during the signal lifecycle (`post_save`).
  - **Time-Based Triggers (`time_based`)**: The filter conditions act as database query parameters when querying eligible records for batch processing.
- **Full Backward Compatibility**: Seamlessly handles legacy flat dictionaries (`{"is_agent": True}`) and flat lists (`[{"field": ...}]`) without requiring database migrations or manual conversion.

### 13.2 Option A Visual Group Builder Component
- Implemented in `automation_reactive_admin.js` as an interactive, hierarchical card tree.
- Uses left-border indented card blocks (`.is-nested` with `border-left: 4px solid #0284c7`) to visually represent mathematical parentheses `(...)`.
- Allows users to nest arbitrary sub-groups (`+ Add Group (...)`) with combinators (`AND` / `OR`).
- Features real-time two-way JSON synchronization writing to `filter_conditions` and mirroring to `condition_rules`.
- Displays dynamic model introspection field dropdowns, field type badges, and inline date formatting reminders.

---

## 14. Action Params Assistant, Persona-Specific Prompt Presets & Template Resolution (Phase 10)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🤖 Action Assistant: hermes_profile:cost_controller             hermes_agent           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Monitor token consumption, track operational budget, and audit expenditures.          │
│                                                                                        │
│ 💡 Quick Action Presets (Click to Load):                                               │
│ [ 📊 Daily Token & Budget Audit ]  [ 🔍 Audit Task Spend ]  [ ⚠️ Budget Overrun Check ]│
│                                                                                        │
│ ⚡ Insert Context Variables:                                                           │
│ [ {{pk}} ] [ {{username}} ] [ {{task_name}} ] [ {{cost_usd}} ] [ {{status}} ] [ {{now}} ]│
│                                                                                        │
│ 📋 Expected Parameters:                                                                │
│ prompt: Natural language task instruction dispatched to the agent                      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 14.1 Interactive Action Params Assistant (`automation_reactive_admin.js`)
- Dynamically rendered in both standalone `AutomationActionAdmin` and inline action rows on `AutomationTriggerAdmin`.
- Binds to `action_type` changes and queries `/api/automation/services/` to load persona descriptions, parameter schemas, and production presets.
- **1-Click Presets**: Immediately populates pre-crafted, production-ready JSON into the `action_params` textarea.
- **Context Variable Insertion**: Displays trigger context variables (`{{pk}}`, `{{task_name}}`, `{{cost_usd}}`, `{{username}}`, `{{status}}`, `{{now}}`), inserting them directly at the cursor position.
- **Schema Guidance**: Explains expected keys and data structures (e.g. `prompt: string`).

### 14.2 Persona-Specific Prompt Presets (`registry.py`)
- Standard presets tailored to the 5 core Nous Research Hermes Agent personas:
  - **`cost_controller`**: Daily token & budget audit, task spend verification against thresholds, budget overrun anomaly alerts.
  - **`qa_auditor`**: Review task output deliverables & submit verdict, scan for hardcoded secrets and unfinished placeholders.
  - **`orchestrator`**: Triage & decompose new intake tasks, synthesize deliverables across sub-tasks.
  - **`comms_agent`**: Draft professional client milestone and progress updates.
  - **`archivist`**: Extract institutional knowledge and SOPs into project documentation.
  - **System Handlers**: Generic webhook payload dispatches, user profile auto-provisioning.

### 14.3 Recursive Template Variable Resolution (`engine.py`)
- In `AutomationEngine.execute_action`, `resolve_nested_template` recursively scans `action_params` data structures (strings, dicts, lists).
- Embedded placeholders like `Audit task #{{pk}} ('{{task_name}}') costing ${{cost_usd}}` are dynamically interpolated at runtime against the in-flight trigger execution context.
- Exact scalar matches (e.g. `{{cost_usd}}` or `{{pk}}`) are coerced cleanly to native numbers or strings.
- Audit logs in `AutomationLog.input_context` capture the resolved parameters for full transparency and reproducibility.

---

## 15. Direct On-Page Automation Execution & Context Builder (Phase 11)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Automation Trigger / Action Change Form                                                │
│                                                     [ ▶ Run Pipeline Now ] [ History ] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Fields & Inlines ...                                                                   │
│                                                                                        │
│ [ Save ]  [ Save and continue editing ]                  [ ▶ Run Pipeline Now ]        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 15.1 Direct On-Page Execution Mechanisms
- **`AutomationTriggerAdmin`**:
  - Top `object-tools` button: `▶ Run Pipeline Now` (`admin:automation_trigger_run_now`).
  - Injected button in `.submit-row` at the bottom of the change form.
  - Action column in changelist view: `▶ Run Pipeline`.
- **`AutomationActionAdmin`**:
  - Top `object-tools` button: `▶ Run Action Now` (`admin:automation_action_run_now`).
  - Injected button in `.submit-row` at the bottom of the change form.
  - Action column in changelist view: `▶ Run Action`.
- **`AutomationActionInline`**:
  - Inline row control: `▶ Run Step #{sequence}: {name}` directly alongside active toggle.

### 15.2 Rich Execution Context Builder (`admin.py`)
- `build_execution_context(model_identifier, user)`:
  - Dynamically inspects the target or trigger model (e.g. `integration.AgentTask`).
  - Extracts field values from the latest live database record (e.g. `pk`, `task_name`, `cost_usd`, `status`).
  - Provides sensible fallback defaults (`task_name="Sample Agent Task"`, `cost_usd=15.50`, etc.) if the table is empty.
  - Injects `username`, `user_id`, `manual_trigger=True`, and `force_execution=True`.
  - Ensures interpolated prompt parameters in `action_params` (e.g. `{{task_name}}`, `{{cost_usd}}`) evaluate cleanly without missing keys.

### 15.3 Engine Manual / Force Execution Support (`engine.py`)
- `AutomationEngine.execute_trigger` and `AutomationEngine.execute_action` support the `force_execution` flag:
  - Bypasses inactive trigger status when an operator explicitly tests an action or pipeline from the admin interface.
  - Skips conditional rule filtering during manual testing, allowing operators to verify action execution and prompt formatting immediately.
  - Records full timing, duration, and structured outputs in `AutomationLog`.

### 15.4 Hermes Agent Gateway Authentication & Timeout Resilience
- **Credential Synchronization**:
  - The backend communicates with the Hermes Gateway daemon (`http://host.docker.internal:8643/v1/chat/completions`) using the `Authorization: Bearer <API_SERVER_KEY>` header.
  - Automatically falls back to `HERMES_API_KEY` from Django settings or environment to ensure seamless authorization.
- **Configurable Timeouts**:
  - Multi-profile agent audits and complex reasoning routines require generous HTTP timeouts.
  - Configurable `HERMES_REQUEST_TIMEOUT = 120` (seconds) introduced in `core/settings.py` and passed to `requests.post(..., timeout=(10, timeout_val))` in `apps.automation.actions.py`.
- **Status Classification**:
  - Responses returning HTTP 4xx/5xx status codes or gateway error bodies are explicitly categorized as `status="failed"` in `AutomationLog` with the full response body captured for debugging.

### 15.5 Action Deduplication & Idempotent Seeding Architecture
- **Pipeline Multi-Action Execution**:
  - `AutomationEngine.execute_trigger` executes all active `AutomationAction` records attached to a trigger in sequence order (`sequence=10, 20...`).
  - To prevent duplicate action dispatches, each trigger maintains a distinct pipeline of action handlers.
- **Idempotent Seeder Reconciliation (`seed_automations.py`)**:
  - Detects and reconciles any legacy auto-generated action records (e.g. `f"{trigger.name} - Action"`) produced during schema migrations.
  - Automatically re-links historical `AutomationLog` audit trails to canonical action records before purging redundant entries, ensuring idempotent runs with zero duplicate action creation.

---

## 16. Core Foundations, Modular App Settings & Bilingual Multi-Language Engine (`apps.core`) (Phase 12)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        apps.core Foundational Architecture                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Abstract Base Models:                                                               │
│    • UUIDModel (Non-enumerable uuid4 PKs)                                              │
│    • TimeStampedModel (Auto-indexed created_at, updated_at)                            │
│    • SoftDeleteModel (Paranoid model: objects.alive() vs all_objects, restore())       │
│    • AuditableModel (Auto created_by / updated_by via contextvars CurrentUserMiddleware)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Odoo-Style Modular Application Settings Framework:                                  │
│    • Declarative App Registration: `@register_settings_group('automation', ...)`       │
│    • Typed Validation: int, str, float, bool, choice, secret, json                     │
│    • Secret Encryption & UI Masking: AES/Signing crypto with `••••••••` masking        │
│    • Dual-Layer Resolution: Redis Cache (TTL) ➔ DB (AppSettingValue) ➔ Code Fallback  │
│    • Unified Settings Hub in Admin: Single-screen view with categorized app sidebar    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Bilingual Multi-Language Engine (English / Arabic):                                 │
│    • GNU gettext extraction & compilation (`locale/ar/LC_MESSAGES/django.mo`)         │
│    • LocaleMiddleware with URL prefix, Cookie, and Accept-Language header resolution   │
│    • BiDi / Native RTL Layout for Arabic with full Django Admin translation            │
│    • User Profile Preference: `preferred_language` on `Profile` with 1-click switching│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 16.1 Abstract Base Models (`apps.core.models`)
- **`TimeStampedModel`**: Standardizes indexed `created_at` and `updated_at` fields across domain models.
- **`UUIDModel`**: Equips domain models with UUIDv4 primary keys to defend external APIs against automated record ID enumeration attacks.
- **`SoftDeleteModel`**: Implements paranoid deletion semantics:
  - Default `objects` manager delegates to `SoftDeleteQuerySet.alive()`, concealing soft-deleted records from standard queries.
  - `all_objects` manager includes soft-deleted records for auditing and recovery.
  - Safe lifecycle methods: `.delete(soft=True)`, `.hard_delete()`, and `.restore()`.
- **`AuditableModel`**: Captures `created_by` and `updated_by` foreign keys to `auth.User`, auto-populated during `save()` via the active request context.

### 16.2 Thread-Safe Request Context Tracking (`apps.core.middleware`)
- Employs Python 3.11's standard `contextvars.ContextVar("current_user")` to capture the authenticated user from `request.user`.
- Context token is guaranteed to reset in a `finally` block upon response delivery, preventing user state leakage across worker threads.
- Enables `AuditableModel.save()` to record audit actors without polluting method signatures or requiring explicit user arguments.

### 16.3 Odoo-Style Modular Application Settings Framework (`apps.core.settings_registry`)
- **App-Scoped Declarations**: Each installed application declares its own configuration parameters cleanly in `conf.py` using `@register_settings_group`.
- **Rich Typed Parameters**: Supports `int`, `str`, `float`, `bool` (toggle switches), `choice` (dropdowns), `secret` (encrypted credentials), and `json`.
- **Cryptographic Secret Protection (`crypto.py`)**: Sensitive values (API keys, webhook signing secrets) are encrypted and signed using Django's `SECRET_KEY` before database persistence, and masked in the UI.
- **Fast Dual-Layer Resolution (`config.py`)**:
  - `get_setting("app.KEY", default=...)` queries Redis cache (`core:setting:<app>:<key>`) first.
  - If missing from cache, queries PostgreSQL `AppSettingValue`.
  - Falls back to registered setting defaults, then Django `settings.py` / `.env`.
  - Signal-based automatic cache invalidation on save and delete guarantees zero-downtime configuration updates across all running Django processes and Celery workers.

### 16.4 Unified Django Admin Settings Hub (`apps.core.admin`)
- Accessible directly at `/admin/core/appsettingvalue/hub/` with a prominent changelist shortcut button.
- Clean Odoo-style visual interface featuring:
  - Left navigation sidebar of installed applications (`⚙️ General Platform`, `⚡ Automation Engine`, `🤖 AI Agents & Hermes`).
  - Native toggle switches for booleans, number steppers, dropdowns for choices, and show/hide toggles for secrets.
  - Instant form persistence updating PostgreSQL and invalidating Redis cache.

### 16.5 Bilingual Multi-Language Architecture (English / Arabic)
- Configured in `core/settings.py` with `LocaleMiddleware`, `LANGUAGES = [('en', 'English'), ('ar', 'العربية')]`, and `LOCALE_PATHS`.
- Compiled Arabic binary translation catalog (`backend/locale/ar/LC_MESSAGES/django.mo`).
- Full BiDi / RTL support automatically formatting Arabic interface layouts.
- User profile preference `Profile.preferred_language` on `apps.integration.models.Profile` exposed in Django Admin user forms.
- DRF content negotiation dynamically resolves localized error messages and responses based on client `Accept-Language` headers.

---

## 17. Metadata Engine, Dynamic Schema & Modular App Runtime (`apps.meta_engine`)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             METADATA-DRIVEN ARCHITECTURE & MODULAR RUNTIME ECOSYSTEM                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [Modular App Packages] (modules/<app_id>/manifest.json)                               │
│       │                                                                                │
│       ▼                                                                                │
│  [AppManifestReader] ────► [DependencyResolver (DAG Topological Sort)]                 │
│                                    │                                                   │
│                                    ▼                                                   │
│                       [Multi-Pass AppInstaller]                                       │
│                       Pass 1: MetaModels & Scalar MetaFields                           │
│                       Pass 2: Relational Foreign Key Links                             │
│                       Pass 3: MetaViews (Forms, Lists, Kanbans)                        │
│                       Pass 4: MetaActions & Hierarchical MetaMenus                     │
│                       Pass 5: MetaReports (CSS Paged Media Templates)                  │
│                                    │                                                   │
│                 ┌──────────────────┴──────────────────┐                                │
│                 ▼                                     ▼                                │
│     [DynamicSchemaEngine]                 [DynamicModelFactory]                        │
│     (Django SchemaEditor DDL)             (In-Memory Compilation)                      │
│     • CREATE / DROP TABLE                 • Compiles (UUID, SoftDelete, Auditable)     │
│     • ADD / DROP COLUMN                   • Registers into django.apps.apps            │
│     • Physical PostgreSQL Tables          • Standard ORM CRUD (filter, save, join)     │
│                 │                                     │                                │
│                 └──────────────────┬──────────────────┘                                │
│                                    ▼                                                   │
│                     [Declarative REST API Gateway]                                     │
│                     • /api/v1/entities/<slug>/ (Polymorphic CRUD)                      │
│                     • /api/v1/entities/<slug>/schema/ (Introspection)                  │
│                     • Row-Level MetaRule Security Evaluation                           │
│                     • DynamicEntitySerializerFactory                                   │
│                                    ▲                                                   │
│                                    │                                                   │
│                     [Odoo-Style Admin App Store]                                       │
│                     • /admin/meta_engine/systemmodule/app-store/                       │
│                     • 1-Click Install / Uninstall with 3 Data Policies                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 17.1 Metadata Catalog Architecture (`apps.meta_engine.models`)
- **`SystemModule`**: Registry tracking discoverable and installed applications, metadata (name, version, category, icon, summary, author), status (`uninstalled`, `installed`, `error`, `to_upgrade`), and dependency graph.
- **`MetaModel`**: Programmatic entity definition (`name`, `label`, `label_plural`, `app_label`, `table_name`, `is_system`, `is_auditable`, `is_soft_delete`, `ordering_field`, `module`).
- **`MetaField`**: Column attributes supporting 12 data types (`char`, `text`, `integer`, `float`, `decimal`, `boolean`, `date`, `datetime`, `json`, `foreign_key`, `many_to_many`, `file`), validation constraints (`required`, `unique`, `index`), choices, default values, and system kernel reserved name protection (`id`, `pk`, `created_at`, `updated_at`, `created_by`, `updated_by`).
- **`MetaView`**: Declarative layout specification storing coordinate and widget schema trees as JSON for forms, lists, kanbans, pivots, and trees.
- **`MetaMenu`**: Hierarchical navigation tree with parent-child nesting, sequence ordering, icons, and action links.
- **`MetaAction`**: Window view actions, server actions, report generation actions, and URL redirects.
- **`MetaRule`**: Row-level access control evaluating `perm_read`, `perm_write`, `perm_create`, `perm_delete`, and dynamic JSON domain expressions (e.g. `{"created_by": "{{user.id}}"}`).
- **`MetaReport`**: Declarative printable report definitions (PDF/HTML) using CSS Paged Media `@page` layout rules, orientation, paper standard (`A4`, `Letter`, `thermal_80mm`), and template interpolation tokens (`{{record.field}}`).

### 17.2 Dynamic PostgreSQL Schema Engine (`apps.meta_engine.schema_engine`)
- Translates `MetaModel` and `MetaField` instances directly into physical database schema modifications via Django's connection `schema_editor()`.
- Direct DDL operations: `create_table()`, `drop_table()`, `add_column()`, `drop_column()`, `table_exists()`, and `column_exists()`.
- Injects standard kernel audit columns (`id` UUID, `created_at`, `updated_at`, `created_by_id`, `updated_by_id`) automatically on table creation.
- Seamless lifecycle signals in `signals.py` synchronize PostgreSQL tables and columns automatically when metadata records change.

### 17.3 Dynamic In-Memory Model Factory (`apps.meta_engine.model_factory`)
- Python metaclass compilation utilizing `type(class_name, bases, attrs)` to produce authentic, live Django Model classes in memory.
- Inherits `(UUIDModel, SoftDeleteModel, AuditableModel)` with zero disk code generation.
- Registered dynamically into `django.apps.apps` for transparent ORM compatibility (filtering, ordering, aggregations, foreign key joins).
- Lazy model resolution on demand via `DynamicModelFactory.get_by_slug(slug)`.

### 17.4 Modular App Lifecycle & DAG Dependency Management
- **Manifest Format (`manifest.json`)**: Self-contained or modular declarations of dependencies, models, fields, views, menus, automations, and reports.
- **Topological Dependency Resolver (`dependency_resolver.py`)**: Resolves dependency DAGs via Kahn's algorithm, calculating optimal installation sequences and blocking cyclic loops (`CyclicDependencyError`) or missing prerequisites (`MissingDependencyError`).
- **Multi-Pass Ingestion (`app_installer.py`)**:
  - Pass 1: Core models and scalar fields (creates tables and columns).
  - Pass 2: Relational links and foreign keys (adds FK constraints across target tables).
  - Pass 3: View layouts, navigation menus, actions, and printable reports.
  - Pass 4: In-memory dynamic model compilation.
- **Safe App Uninstaller & Data Retention Policies (`app_uninstaller.py`)**:
  - Reverse Dependency Guard: Blocks uninstallation of modules if another active module depends on them.
  - 3 Data Retention Policies:
    1. `archive`: Conceals models, views, and menus while preserving physical tables and records.
    2. `snapshot_backup_and_drop`: Serializes table records to JSON snapshot file in `media/module_backups/` before dropping DDL.
    3. `cascade_drop`: Drops metadata assets and physical PostgreSQL tables immediately.

### 17.5 Universal Declarative REST API Gateway (`apps.meta_engine.views`)
- Single unified REST endpoint family mounted at `/api/v1/entities/<model_slug>/`:
  - `GET /api/v1/entities/<model_slug>/`: List records with pagination, filtering, ordering, and full-text search.
  - `POST /api/v1/entities/<model_slug>/`: Create record with automatic user audit attribution.
  - `GET /api/v1/entities/<model_slug>/<id>/`: Retrieve single record.
  - `PUT / PATCH /api/v1/entities/<model_slug>/<id>/`: Update record.
  - `DELETE /api/v1/entities/<model_slug>/<id>/`: Delete record (or soft-delete if enabled).
  - `GET /api/v1/entities/<model_slug>/schema/`: Full declarative introspection of fields, views, and printable reports.
- Dynamic serializers via `DynamicEntitySerializerFactory`.
- Row-level `MetaRule` enforcement evaluating user group permissions and interpolating dynamic domain filters (e.g. `{{user.id}}`).

### 17.6 Odoo-Style Admin App Store Interface (`apps.meta_engine.admin`)
- Accessible at `/admin/meta_engine/systemmodule/app-store/` with changelist toolbar button.
- Card grid UI with icons, version badges, categories, summaries, dependencies, and 1-click install/uninstall actions.
- Integrated disk synchronization ("🔄 Scan Disk for Modules").
- Live PostgreSQL DDL status badges and direct REST API gateway links in `MetaModelAdmin`.

---

## 18. Multi-Tenancy, Organizations & Workspaces Architecture (Phase 14)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        🌐 Incoming Request / API / Celery Task                         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │      TenantMiddleware Resolution Strategy     │
                    │ 1. Header: X-Workspace-Slug / Organization-ID │
                    │ 2. Query Param: ?workspace=<slug>             │
                    │ 3. Subdomain / Domain: <slug>.platform.com    │
                    │ 4. Authenticated User Default Membership       │
                    │ 5. Global Fallback: "default" Workspace       │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │   Python 3.11 contextvars Tenant Scope        │
                    │   _current_tenant_ctx.set(organization)       │
                    │   (guaranteed token reset in finally block)   │
                    └───────────────────────┬───────────────────────┘
                                            │
             ┌──────────────────────────────┴──────────────────────────────┐
             ▼                                                             ▼
┌─────────────────────────────┐                               ┌─────────────────────────────┐
│    Static Stored Models     │                               │  Declarative Dynamic Models │
│  (TenantAwareModel Bases)   │                               │  (apps.meta_engine Factory) │
│ - Organization FK (indexed) │                               │ - is_tenant_aware = True    │
│ - Automatic tenant on save  │                               │ - Compiles TenantAwareModel │
│ - TenantManager filtering   │                               │ - DDL organization_id col   │
└────────────┬────────────────┘                               └──────────────┬──────────────┘
             │                                                             │
             └──────────────────────────────┬──────────────────────────────┘
                                            │
                                            ▼
                       ┌────────────────────────────────────────┐
                       │  Row-Level Scoped QuerySet Execution   │
                       │  .filter(organization=current_tenant)  │
                       │  (Unfiltered via TenantAllManager /    │
                       │   bypass_tenant_isolation() context)   │
                       └────────────────────────────────────────┘
```

### 18.1 Tenant Representation & RBAC Hierarchy (`apps.tenants.models`)
- **`Organization`**:
  - Inherits `(UUIDModel, SoftDeleteModel, AuditableModel)`.
  - Fields: `name`, `slug` (unique, db_index), `tier` (`free`, `starter`, `pro`, `enterprise`), `max_users` (seat limit), `domain` (custom domain / email domain), `is_active`, and `metadata` (JSON configuration).
  - Helper methods: `active_members_count`, `can_add_user()`, `get_owner()`, `is_member(user)`.
- **`OrganizationMembership`**:
  - Junction linking `auth.User` to `Organization` with unique constraint `(organization, user)`.
  - Granular Workspace Roles: `owner` (full workspace ownership & deletion), `admin` (member & invitation management), `member` (standard operational access), `viewer` (read-only), `guest` (restricted).
  - Validates seat capacity on creation via `clean()`.
- **`OrganizationInvitation`**:
  - Expiring, tokenized invitations (`secrets.token_urlsafe(64)`).
  - Lifecycles: `pending` → `accepted` | `expired` | `revoked`.
  - Atomic `accept(user)` method creating membership and timestamping acceptance.

### 18.2 Row-Level Tenant Isolation via TenantAwareModel (`apps.tenants.base_models`)
- **`TenantAwareModel(AuditableModel)`**:
  - Abstract base model ensuring every tenant-scoped entity carries an indexed foreign key to `Organization`.
  - Nullable with fallback: `organization = models.ForeignKey(..., null=True, blank=True)` preventing migration deadlocks and supporting system-wide templates.
  - Auto-population in `save()`: Binds `self.organization` to `get_current_tenant()` (or system default workspace) if omitted.
- **`TenantManager` & `TenantQuerySet` (`apps.tenants.managers`)**:
  - Automatically applies `is_deleted=False` (via integrated `SoftDeleteQuerySet.alive()`) and `.filter(organization=get_current_tenant())`.
  - Provides convenience helpers: `.alive()`, `.dead()`, `.restore()`, `.hard_delete()`.
- **`TenantAllManager`**:
  - Exposed via `Model.all_objects` to allow explicit unfiltered access for migrations, global analytics, and superuser maintenance.

### 18.3 Thread-Safe ContextVars Context Management (`apps.tenants.context`)
- Avoids thread-local memory leakage across worker threads by utilizing Python 3.11's `contextvars.ContextVar`.
- Public API:
  - `get_current_tenant() -> Optional[Organization]`
  - `set_current_tenant(organization) -> Token`
  - `clear_current_tenant(token=None)`
  - `tenant_context(organization)`: Scoped execution context manager.
  - `bypass_tenant_isolation()`: Scoped bypass context manager for cross-tenant operations.

### 18.4 Multi-Strategy Tenant Resolution Middleware (`apps.tenants.middleware`)
- Multi-tier resolution order:
  1. HTTP Header: `X-Workspace-Slug` or `X-Organization-ID` (UUID or slug).
  2. Query Parameter: `?workspace=<slug>`.
  3. Host domain or subdomain: `<slug>.domain.com` or custom domain.
  4. Authenticated user's default active membership.
  5. Global system default workspace (`Default Workspace`, slug: `default`).
- Security gate: If an explicit workspace is requested, verifies that `request.user` has active membership (superusers bypass check). Non-members receive `403 Forbidden`.

### 18.5 Declarative MetaEngine Integration
- **`MetaModel.is_tenant_aware`**: Boolean flag (default `True`) instructing the engine to partition dynamic entity records by tenant.
- **Dynamic Model Factory**: Injects `TenantAwareModel` into compiled model bases, compiling dynamic models with `organization` foreign key and `TenantManager`.
- **Dynamic Schema Engine**: Automatically generates `organization_id` foreign key column pointing to `tenants_organization` in physical PostgreSQL tables.
- **Universal Declarative REST API Gateway**: In `UniversalEntityViewSet`, queries are auto-scoped by tenant, and new records automatically bind to `get_current_tenant()`.

### 18.6 Administrative & REST API Surface (`apps.tenants.views` & `admin`)
- **`OrganizationViewSet` (`/api/v1/organizations/`)**:
  - Full CRUD with membership filtering (superusers see all; regular users see their active workspaces).
  - Creator is automatically assigned as `owner`.
  - Action `@action(detail=True) members`: List and add members.
  - Action `@action(detail=True) invite`: List pending invitations and dispatch new invites.
  - Action `@action(detail=True) switch`: Verify membership and return active workspace header hints.
- **`InvitationAcceptAPIView` (`/api/v1/invitations/<token>/accept/`)**: Self-service invitation token validation and membership activation.
- **Django Admin**: `OrganizationAdmin` with `OrganizationMembershipInline`, user capacity badges, tier styling, and invitation revocation actions.

---

## 19. Comprehensive Activity Audit Trail Architecture (`apps.audit`) (Phase 15)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              Enterprise Activity Audit Trail & Compliance Architecture                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [Incoming HTTP Request / REST API]               [Celery Worker / Background Task]    │
│            │                                                    │                      │
│            ▼                                                    ▼                      │
│  [AuditContextMiddleware]                             [with audit_context(...):]       │
│  • Extracts Client IP (Forwarded/Real/Remote)         • Binds actor, IP, req_id        │
│  • Extracts User-Agent & Correlation ID               • Binds custom metadata          │
│  • Binds to contextvars (_client_ip_ctx, etc.)        • Cleans context in finally      │
│  • Injects X-Request-ID into Response Headers                                          │
│            │                                                    │                      │
│            └─────────────────────────┬──────────────────────────┘                      │
│                                      │                                                 │
│                                      ▼                                                 │
│                      ┌───────────────────────────────┐                                 │
│                      │  Django Model Lifecycle Hooks │                                 │
│                      │   pre_save, post_save, delete │                                 │
│                      └───────────────┬───────────────┘                                 │
│                                      │                                                 │
│                        ┌─────────────┴─────────────┐                                   │
│                        ▼                           ▼                                   │
│             [Static Auditable Models]    [Dynamic MetaEngine Models]                   │
│             (@register_auditable or      (meta_model.is_auditable=True,                │
│              _audit_enabled = True)       DynamicModelFactory auto-reg)                │
│                        │                           │                                   │
│                        └─────────────┬─────────────┘                                   │
│                                      │                                                 │
│                                      ▼                                                 │
│                      ┌───────────────────────────────┐                                 │
│                      │   Attribute Diffing Engine    │                                 │
│                      │   (apps.audit.signals)        │                                 │
│                      │ • Excludes auto timestamps    │                                 │
│                      │ • Masks sensitive credentials │                                 │
│                      │ • Suppresses zero-diff noise  │                                 │
│                      │ • Maps soft delete / restore  │                                 │
│                      └───────────────┬───────────────┘                                 │
│                                      │                                                 │
│                                      ▼                                                 │
│                      ┌───────────────────────────────┐                                 │
│                      │     ActivityLog Repository    │                                 │
│                      │ • GenericForeignKey target    │                                 │
│                      │ • Integer & UUID PK support   │                                 │
│                      │ • Immutable save() & delete() │                                 │
│                      │ • Immutable QuerySet bulk ops │                                 │
│                      └───────────────┬───────────────┘                                 │
│                                      │                                                 │
│                 ┌────────────────────┴────────────────────┐                            │
│                 ▼                                         ▼                            │
│    [Read-Only Django Admin]                  [Read-Only REST API Gateway]              │
│    • Visual Before/After Diff Table          • GET /api/v1/audit/logs/                 │
│    • Colored Action & Status Badges          • Scoped to active tenant                 │
│    • Blocked add/change/delete               • Multi-parameter filter & search         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 19.1 Immutable Storage & Generic Relationship Schema (`apps.audit.models`)
- **`ActivityLog`**:
  - Primary Key: Distributed UUIDv4 (`UUIDModel`).
  - Actor Types: `user` (human), `bot` (service account), `system` (background daemon), `anonymous`.
  - Actions: `create`, `update`, `delete` (soft), `restore`, `hard_delete`, `login`, `logout`, `login_failed`, `export`, `custom`.
  - Status: `success`, `failure`, `warning`.
  - Polymorphic Target (`GenericForeignKey`):
    - `content_type`: `ForeignKey(ContentType, on_delete=SET_NULL, null=True, db_index=True)`.
    - `object_id`: `CharField(max_length=255, null=True, blank=True, db_index=True)`.
    - Stringified `object_id` seamlessly stores standard integer primary keys (`auth.User`, `AppSettingValue`) and non-enumerable UUID primary keys (`Organization`, `MetaModel`, dynamic models).
  - Multi-Tenant Scoping:
    - Nullable `organization` foreign key allowing both tenant-partitioned audit trails and global system-level events (e.g. system bot scheduler boot, platform healthchecks).
  - Structured Diffs & Telemetry:
    - `changes`: `JSONField(default=dict)` storing `{"field": {"old": val1, "new": val2}}`.
    - `ip_address`: `GenericIPAddressField(null=True, blank=True)`.
    - `user_agent`: `TextField(blank=True)`.
    - `request_id`: `CharField(max_length=64, blank=True, db_index=True)`.
    - `metadata`: `JSONField(default=dict)` for contextual trace parameters.
- **Dual-Layer Immutability Enforcers**:
  - `ActivityLog.save()`: Raises `ImmutabilityError(PermissionDenied)` if updating an existing persisted record.
  - `ActivityLog.delete()`: Raises `ImmutabilityError` unless explicitly called with `allow_purge=True`.
  - `ActivityLogQuerySet.update()`: Disallows bulk SQL updates on QuerySets.
  - `ActivityLogQuerySet.delete()`: Disallows bulk SQL deletions unless `allow_purge=True` is provided.

### 19.2 Request Context & Client Telemetry Middleware (`apps.audit.context` & `middleware`)
- **Python 3.11 `contextvars` Engine**:
  - `_client_ip_ctx`, `_user_agent_ctx`, `_request_id_ctx`, `_audit_actor_ctx`, `_audit_metadata_ctx`.
  - Functions: `get_audit_ip()`, `get_audit_user_agent()`, `get_audit_request_id()`, `get_audit_actor()`, `get_audit_metadata()`.
  - Context Manager: `with audit_context(actor=..., ip=..., request_id=...):` for background tasks, celery workers, and test scopes.
- **`AuditContextMiddleware`**:
  - Extracts client IP address with proxy / CDN defense (`HTTP_X_FORWARDED_FOR`, `HTTP_X_REAL_IP`, `REMOTE_ADDR`).
  - Extracts `HTTP_USER_AGENT`.
  - Resolves or generates correlation ID (`HTTP_X_REQUEST_ID`, `HTTP_X_CORRELATION_ID`, or `req_<hex>`), attaching `request.id` and setting the `X-Request-ID` response header.
  - Binds contextvars before view processing and guarantees reset in a `finally` block to prevent thread state contamination.

### 19.3 Automated Lifecycle Diffing & Security Signals (`apps.audit.signals`)
- **Noise Suppression & Hygiene**:
  - Excludes auto-updating timestamp fields (`updated_at`, `modified_at`).
  - Masks sensitive credentials (`password`, `token`, `secret`, `api_key`) as `"[PROTECTED]"`.
  - Suppresses empty audit log generation when `save()` is executed with no attribute changes.
- **Signal Handlers**:
  - `pre_save`: Queries database for original record snapshot (using `all_objects` or `_base_manager` to safely inspect soft-deleted records) and caches `_audit_old_snapshot`.
  - `post_save`:
    - New record (`created=True`) -> generates `ACTION_CREATE` with initial field values.
    - Existing record -> compares old vs new values.
    - Soft-delete detection: if `is_deleted` transitions `False -> True`, records `ACTION_DELETE`; if `True -> False`, records `ACTION_RESTORE`; otherwise `ACTION_UPDATE`.
  - `post_delete`: Records `ACTION_HARD_DELETE` with snapshot of prior record attributes.
- **Authentication Security Event Receivers**:
  - `user_logged_in`: Logs `ACTION_LOGIN` (`STATUS_SUCCESS`) with actor, target user, IP, and User-Agent.
  - `user_logged_out`: Logs `ACTION_LOGOUT` (`STATUS_SUCCESS`).
  - `user_login_failed`: Logs `ACTION_LOGIN_FAILED` (`STATUS_FAILURE`) with attempted username and client IP for intrusion detection.

### 19.4 Dynamic MetaEngine Declarative Integration
- `MetaModel.is_auditable`: Declarative schema flag.
- When `DynamicModelFactory` compiles an in-memory Django model from a `MetaModel` where `is_auditable=True`:
  - Injects `_audit_enabled = True` attribute on the dynamic model class.
  - Registers dynamic class into `apps.audit.registry._AUDITABLE_MODELS`.
  - Full CRUD operations on dynamic entities automatically emit `ActivityLog` entries with before/after diffs and tenant attribution.

### 19.5 Administrative & REST API Surface (`apps.audit.admin` & `views`)
- **`ActivityLogAdmin`**:
  - Strictly read-only: `has_add_permission`, `has_change_permission`, and `has_delete_permission` unconditionally return `False`.
  - Custom visual diff card (`changes_diff_card`): Renders before/after changes as an HTML comparison table with styled line-through red badges for prior values and green badges for new values.
  - Colored action badges (`action_badge`): Emerald (create), Blue (update), Amber (soft delete), Cyan (restore), Red (hard delete), Purple (login), Gray (logout), Crimson (login failed).
  - Colored status badges (`status_badge`): Green (success), Red (failure), Yellow (warning).
- **`ActivityLogViewSet` (`/api/v1/audit/logs/`)**:
  - Read-only (`ReadOnlyModelViewSet`) exposing `list` and `retrieve`.
  - Multi-tenant query scoping: auto-filters by active organization (`get_current_tenant()`) for non-superusers.
  - Filtering by `action`, `actor_type`, `status`, `request_id`, `object_id`.
  - Full-text search across `object_repr`, `object_id`, and `actor__username`.
  - Mutation endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) return `405 Method Not Allowed`.






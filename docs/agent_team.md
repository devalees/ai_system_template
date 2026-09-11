# Hermes Agent Team: Autonomous Workforce Specification

A profile-centric reference and planning document detailing each autonomous agent in the Hermes workforce, their individual responsibilities, dedicated skills, executable scripts, and inter-agent routing flows.

- **Status**: ACTIVE SPECIFICATION & PLANNING BASELINE
- **File**: [`docs/agent_team.md`](file:///home/ehab/Desktop/economy_editor/docs/agent_team.md)
- **Container Runtime**: Hermes Agent Container (`hermes-template-agent`), isolated network (`hermes_isolated_network`)
- **Backend Bridge**: Django REST API (`http://host.docker.internal:8000/api`) with Token Authentication & RBAC

---

## 1. Team Architecture Overview

The autonomous workforce operates under a decentralized division of labor:
- Each agent runs as an isolated persona within the Hermes runtime (`/root/.hermes/profiles/<name>/`).
- Each agent corresponds to a dedicated Django Service Account (`bot_<name>`) bound to native Django permissions (Principle of Least Privilege).
- Tasks are tracked in the PostgreSQL `AgentTask` registry and orchestrated through `apps.automation` Celery pipelines.

```
agent_service/
├── profiles/
│   ├── orchestrator/      # 1. Chief of Staff & Kanban Router
│   │   └── skills/task_decomposer/  # Profile-scoped DAG planner & dependency validator
│   ├── cost_controller/   # 2. Financial Controller & Budget Monitor
│   │   └── skills/cost_monitor/  # Profile-scoped SQLite spend auditor
│   ├── qa_auditor/        # 3. QA & Compliance Gatekeeper
│   │   └── skills/output_validator/ # Profile-scoped AST syntax & deliverable hygiene validator
│   ├── comms_agent/       # 4. Client Communications Coordinator
│   │   └── skills/client_service_bridge/ # Profile-scoped client concierge bridge
│   └── security_guard/    # 5. Security & Threat Auditor (SecOps)
│       └── skills/security_scanner/ # Profile-scoped zero-trust security auditor
└── skills/
    └── django_handshake/  # Shared system connectivity & health skill
```

---

## 2. Agent Profiles: Specifications, Skills & Scripts

---

### Agent 1: Orchestrator (`orchestrator`)

- **Role**: Chief of Staff / Request Intake & Kanban Router
- **Directory**: [`agent_service/profiles/orchestrator/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/orchestrator/)
- **Service Account**: `bot_orchestrator` | **Django Group**: `Agent_Orchestrator`
- **Permissions**: `view_agentprofile`, `view_agenttask`, `add_agenttask`, `change_agenttask`
- **Calibrated Reasoning**: `none` (0-second latency for instant triage and routing)
- **Default Toolsets**: `kanban`, `delegate`, `terminal`, `file_ops`, `clarify` (Locked; heavy tools excluded)
- **Bundled Skills Opt-Out**: `.no-bundled-skills` active (pruned 54 bundled skills to prevent prompt bloat)

#### Primary Responsibilities
- **Request Intake**: Ingests incoming system prompts, automation triggers, or client requests.
- **Decomposition**: Breaks complex projects into atomic sub-tasks and registers them in `AgentTask`.
- **Kanban Routing**: Assigns sub-tasks to specialist agent profiles or spawns ephemeral sub-agents.
- **Deliverable Synthesis**: Aggregates completed outputs into a unified final delivery.

#### Dedicated Skills & Scripts
- **Skill**: **`task_decomposer`** ([`agent_service/profiles/orchestrator/skills/task_decomposer/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/orchestrator/skills/task_decomposer/))
  - **Executable Script**: [`agent_service/profiles/orchestrator/skills/task_decomposer/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/orchestrator/skills/task_decomposer/run.py)
  - **What It Does**:
    1. Parses high-level objectives into a structured execution pipeline across the 5 department roles (`orchestrator`, `cost_controller`, `qa_auditor`, `comms_agent`, `security_guard`).
    2. Enforces explicit dependency mapping and sequential DAG validation (cycle detection prevents execution deadlocks).
    3. Direct-submits decomposed tasks to the Django task queue (`POST /api/tasks/`) using `bot_orchestrator`'s API token when executed with `--submit`.
    4. Supports `--dry-run` and `--json` export for inspection and dry evaluation before dispatch.
- **Dynamic Task Delegation**: Uses Hermes native `delegate` tool to spawn ephemeral sub-agents for parallel work.
- **Kanban Dispatch**: Interacts with the backend task queue via `POST /api/tasks/` to register and reassign workloads.

---

### Agent 2: Cost Controller (`cost_controller`)

- **Role**: Financial Controller / Token Consumption & Budget Auditor
- **Directory**: [`agent_service/profiles/cost_controller/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/cost_controller/)
- **Service Account**: `bot_cost_controller` | **Django Group**: `Agent_CostController`
- **Permissions**: `view_spendreport`, `add_spendreport`, `view_agentprofile` *(Explicitly blocked from creating/modifying tasks)*
- **Calibrated Reasoning**: `low` (sufficient for calculations without token waste)
- **Default Toolsets**: `terminal`, `file_ops` (Locked; web and bundled media tools excluded)
- **Bundled Skills Opt-Out**: `.no-bundled-skills` active (pruned 54 bundled skills to eliminate token overhead)

#### Primary Responsibilities
- **Token Tracking**: Scans LLM token consumption across all agent sessions in real time.
- **Budget Governance**: Enforces daily expenditure ceilings (`DAILY_BUDGET_CAP_USD`).
- **Spend Reporting**: Compiles and pushes audit reports to the Django backend.
- **Overrun Alerts**: Flags anomalous spikes and triggers pause actions if budgets are exceeded.
- **Model Efficiency Advisory**: Evaluates Intelligence-per-Dollar ROI using frontier benchmarks (DeepSWE) and recommends cheaper, high-accuracy alternatives.

#### Dedicated Skills & Scripts
- **Skill**: **`cost_monitor`** ([`agent_service/profiles/cost_controller/skills/cost_monitor/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/cost_controller/skills/cost_monitor/))
  - **Executable Script**: [`agent_service/profiles/cost_controller/skills/cost_monitor/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/cost_controller/skills/cost_monitor/run.py)
  - **What It Does**:
    1. Scans SQLite databases (`state.db`) across all profiles in `/root/.hermes/profiles/`.
    2. Queries the `session_model_usage` table for prompt and completion token counts per model.
    3. Calculates estimated dollar costs using reference pricing tiers.
    4. Evaluates total spend against the `--daily-budget` parameter.
    5. Queries Django's model benchmark registry (`GET /api/hermes/benchmarks/`) to calculate Intelligence-to-Cost ratios ($ROI = \text{score} / \text{cost}$).
    6. Automatically generates cost-efficiency recommendations when alternative models offer equal or higher pass rates at lower cost.
    7. Dispatches structured `SpendReport` and recommendations directly to `POST /api/spend-reports/` when invoked with `--push`.

---

### Agent 3: QA Auditor (`qa_auditor`)

- **Role**: Quality Assurance & Compliance Gatekeeper
- **Directory**: [`agent_service/profiles/qa_auditor/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/qa_auditor/)
- **Service Account**: `bot_qa_auditor` | **Django Group**: `Agent_QAAuditor`
- **Permissions**: `view_agenttask`, `change_agenttask`, `view_agentprofile` *(Exclusive authorization to submit review verdicts)*
- **Calibrated Reasoning**: `high` (deep analytical reasoning for rigorous inspection)
- **Default Toolsets**: `kanban`, `terminal`, `file_ops` (Locked strictly; unneeded media/creative tools excluded)
- **Bundled Skills Opt-Out**: `.no-bundled-skills` active (pruned 54 bundled skills to eliminate token overhead)

#### Primary Responsibilities
- **Syntactic & Deliverable Gatekeeper**: Serves as the mandatory review checkpoint before any task is marked `completed`.
- **Syntax & Structural Integrity**: Verifies that generated Python code, JSON/YAML schemas, and documentation compile and parse without syntax errors.
- **Pre-Commit Hygiene Seatbelt**: Catches leftover stub placeholders (`TODO`, `FIXME`, `CHANGEME`, `NotImplementedError`) and obvious unmasked credentials before deliverables are merged.
- **Authoritative Review Verdicts**: Submits binding decisions (`approved` or `changes_requested`) to the Django review gate.

#### Dedicated Skills & Scripts
- **Skill**: **`output_validator`** ([`agent_service/profiles/qa_auditor/skills/output_validator/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/qa_auditor/skills/output_validator/))
  - **Executable Script**: [`agent_service/profiles/qa_auditor/skills/output_validator/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/qa_auditor/skills/output_validator/run.py)
  - **What It Does**:
    1. **Multi-Format Syntax Compilation**: Compiles Python AST (`ast.parse`) to detect syntax errors; decodes JSON/YAML schemas; verifies Markdown code fences and formatting.
    2. **Placeholder Trapping**: Scans files for unfinished markers (`TODO`, `FIXME`, `CHANGEME`, stubbed passes).
    3. **Defense-in-Depth Leak Seatbelt**: Performs a fast regex scan for obvious API keys or private keys as a safety net (comprehensive vulnerability auditing, tenant isolation, and gateway threats are governed by `security_guard`).
    4. **Scoring & Verdict**: Generates a 0–100 quality score and emits an authoritative verdict (`APPROVED` vs `CHANGES_REQUESTED`).
    5. **Direct Review Gate Dispatch**: Direct-submits verdict and structured defect notes to Django via `POST /api/tasks/<id>/submit-verdict/` when executed with `--submit --task-id <UUID>` using `bot_qa_auditor`'s API token.


---

### Agent 4: Comms Agent (`comms_agent`)

- **Role**: Client Service & Communications Coordinator
- **Directory**: [`agent_service/profiles/comms_agent/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/comms_agent/)
- **Service Account**: `bot_comms_agent` | **Django Group**: `Agent_CommsAgent`
- **Permissions**: `view_agenttask`, `view_agentprofile`, `view_document`
- **Calibrated Reasoning**: `none` (zero thinking latency and minimal token consumption for real-time client assistance)
- **Default Toolsets**: `terminal`, `file_ops` (Locked strictly; web and bundled media tools excluded)
- **Bundled Skills Opt-Out**: `.no-bundled-skills` active (pruned 54 bundled skills to eliminate token overhead)

#### Primary Responsibilities
- **External Concierge & Intake**: Serves as the primary external touchpoint for external clients ([`apps.clients.models.Client`](file:///home/ehab/Desktop/economy_editor/backend/apps/clients/models.py)) and their associated representative users (`Profile.client`), answering inquiries and providing structured project visibility. External clients interact exclusively with `comms_agent`.
- **Zero-Trust Document Streaming**: Strictly requests client-authorized attachments via authenticated Django REST endpoints (`GET /api/v1/media/documents/<id>/download/`) with tenant/client ownership validation and SOC2/GDPR audit logging (`apps.audit`). Never accesses global backend filesystem mounts directly.
- **Engagement-Budgeted Governance**: Enforces the client's `is_ai_enabled` permission and monitors dollar spend against allocated ceilings (`Client.ai_budget_usd`) across 4 percentage milestones (25% silent audit, 50% velocity check, 75% proactive advisory notice, 100% quota escalation) via `client_budget_status`.
- **Notification Bridging**: Dispatches messages across system channels (In-App, Email, Webhook, Slack) via `apps.notifications`.

#### Dedicated Skills & Scripts
- **Skill**: **`client_service_bridge`** ([`agent_service/profiles/comms_agent/skills/client_service_bridge/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/comms_agent/skills/client_service_bridge/))
  - **Executable Script**: [`agent_service/profiles/comms_agent/skills/client_service_bridge/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/comms_agent/skills/client_service_bridge/run.py)
  - **What It Does**:
    1. **`budget-check`**: Queries Django for the client's active entitlement (`is_ai_enabled`), current AI spend, allocated dollar budget, percentage tier, and threshold actions; optionally increments spend via `--log-spend`.
    2. **`status`**: Fetches client account status, active tenant, and engagement progress.
    3. **`documents`**: Queries accessible document inventory for the authenticated client context.
    4. **`fetch-doc`**: Securely streams and downloads a document via authenticated REST API, inspects content, and enables immediate transient file unlinking (`os.unlink()`).
    5. **`notify`**: Dispatches multi-channel client notifications via `apps.notifications.dispatcher.NotificationDispatcher`.

---

### Agent 5: Security Guard (`security_guard`)

- **Role**: Security & Threat Auditor (SecOps)
- **Directory**: [`agent_service/profiles/security_guard/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/security_guard/)
- **Service Account**: `bot_security_guard` | **Django Group**: `Agent_SecurityGuard`
- **Permissions**: `view_agenttask`, `view_profile`, `view_activitylog`, `view_apikey`, `view_webhookevent`
- **Calibrated Reasoning**: `high` (deep analytical reasoning for strict security, access boundary, and leak audits)
- **Default Toolsets**: `terminal`, `file_ops` (Locked strictly; media/creative tools excluded)
- **Bundled Skills Opt-Out**: `.no-bundled-skills` active (pruned 54 bundled skills to eliminate token overhead)

#### Primary Responsibilities
- **Zero-Trust Sentinel**: Enforces a strict Zero-Trust philosophy across all deliverables, client interactions, and backend data flows (*Never trust, always verify*).
- **Credential & Secret Leak Prevention**: Scans deliverables, configuration files, and `.env` runtimes for leaked API keys (OpenAI, OpenRouter, Anthropic, Stripe), tokens, and private cryptographic certificates.
- **Tenant Boundary & Least Privilege Auditing**: Verifies that ORM queries and REST views strictly enforce `TenantAwareModel` or `tenant_context`, ensuring no cross-tenant leakage. Audits service accounts (`bot_*`) to prevent privilege escalation.
- **API Gateway & Webhook Threat Monitoring**: Audits `WebhookEvent` logs for failed HMAC signature verifications and inspects `ActivityLog` for anomalous login bursts or suspicious IP spikes.

#### Dedicated Skills & Scripts
- **Skill**: **`security_scanner`** ([`agent_service/profiles/security_guard/skills/security_scanner/`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/security_guard/skills/security_scanner/))
  - **Executable Script**: [`agent_service/profiles/security_guard/skills/security_scanner/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/profiles/security_guard/skills/security_scanner/run.py)
  - **What It Does**:
    1. **`secrets-scan`**: Scans target directories or files for unmasked credentials, tokens, and private keys with severity ratings (`CRITICAL`, `HIGH`, `MEDIUM`). Supports `--exclude-tests` to focus strictly on production code.
    2. **`tenant-audit`**: Introspects Django model inheritance to ensure domain models inherit `TenantAwareModel`.
    3. **`rbac-audit`**: Verifies that active service accounts adhere to Principle of Least Privilege matrices.
    4. **`gateway-audit`**: Checks active security posture: HMAC signature enforcement, SHA-256 hashed API keys, and IP allowlist guards.
    5. **`--json`**: Emits structured JSON reports for automated pipeline processing and alert dispatch.

---

## 3. Shared System Skills & Provisioning Scripts

These scripts support the team's infrastructure, connectivity, and lifecycle management.

| Script / Skill | Location | Purpose |
| :--- | :--- | :--- |
| **`django_handshake`** | [`agent_service/skills/django_handshake/run.py`](file:///home/ehab/Desktop/economy_editor/agent_service/skills/django_handshake/run.py) | Probes backend health (`GET /api/health/`), submits container handshake (`POST /api/handshake/`), confirms PostgreSQL persistence. |
| **`provision_profiles.py`** | [`scripts/provision_profiles.py`](file:///home/ehab/Desktop/economy_editor/scripts/provision_profiles.py) | Synchronizes profile folders to Hermes container runtime (`/root/.hermes/profiles/`), fetches bot tokens from Django, writes runtime `.env` files. |
| **`verify_handshake.py`** | [`scripts/verify_handshake.py`](file:///home/ehab/Desktop/economy_editor/scripts/verify_handshake.py) | Empirically tests cross-container reachability and verifies API handshakes. |

---

## 4. Inter-Agent Task Routing & Interaction Lifecycle

Tasks follow a deterministic, auditable route through the team:

```mermaid
flowchart TD
    Trigger([1. User Request / Event Trigger]) --> Orch[Orchestrator]
    
    subgraph S1 ["Stage 1: Intake & Triage"]
        Orch -->|Decompose & Register| TaskReg[(Django AgentTask: Pending)]
    end
    
    subgraph S2 ["Stage 2: Specialist Execution"]
        TaskReg -->|Assign Task| ExecAgent[Specialist Agent / Sub-Agent]
        ExecAgent -->|Execute & Deliver| Artifacts[Code / Artifacts / Outputs]
        Artifacts -->|Transition: Review| ReviewState[(AgentTask: In Review)]
    end
    
    subgraph S3 ["Stage 3: Quality Gate"]
        ReviewState --> QA[QA Auditor]
        QA -->|Run output_validator| ValScript[skills/output_validator/run.py]
        ValScript --> Verdict{Verdict?}
        Verdict -->|Changes Requested| ExecAgent
        Verdict -->|Approved| ApprovedState[(AgentTask: Completed)]
    end
    
    subgraph S4 ["Stage 4: Cost Audit"]
        ApprovedState --> Cost[Cost Controller]
        Cost -->|Run cost_monitor| CostScript[skills/cost_monitor/run.py]
        CostScript -->|Post SpendReport| SpendDB[(PostgreSQL SpendReport)]
    end
    
    subgraph S5 ["Stage 5: Security & Client Handoff"]
        ApprovedState --> Sec[Security Guard]
        Sec -->|Run security_scanner| SecScript[skills/security_scanner/run.py]
        ApprovedState --> Comms[Comms Agent]
        Comms -->|Draft & Send Update| Stakeholder([Client / Channel Notification])
    end
```

### Step-by-Step Flow:
1. **Intake (`orchestrator`)**: Ingests the task, creates structured `AgentTask` records, and assigns them to the appropriate specialist.
2. **Execution (Specialist / Sub-Agent)**: The executing agent works on the task and transitions status from `pending` ➔ `in_progress` ➔ `review`.
3. **QA Review Gate (`qa_auditor`)**: `qa_auditor` inspects deliverables using `output_validator`. If clean, it marks `approved`. If defective, it submits `changes_requested` with structured notes and loops back to the executor.
4. **Spend Audit (`cost_controller`)**: Evaluates token consumption and updates `SpendReport`. If spend exceeds budget thresholds, alerts are triggered.
5. **Security & Threat Audit (`security_guard`)**: Evaluates deliverables for credential leaks, validates multi-tenant isolation, and audits access permissions.
6. **Client Handoff (`comms_agent`)**: Composes external-facing summaries and notifies stakeholders.

---

## 5. Discussion & Planning Agenda

Use this section as the launching pad for team refinement:

1. **Role Expansion**:
   - Do we need a dedicated `security_auditor` or `backend_developer` profile?
   - What specific toolsets should each new role possess?
2. **Skill Library Expansion**:
   - What recurring workflows should be packaged into new skills in `agent_service/skills/` (e.g. automated test runner, API contract tester, database migration validator)?
3. **Routing Enhancements**:
   - How should handoffs be coordinated: via deterministic Celery pipelines, or dynamic autonomous delegation by `orchestrator`?
   - Should QA gate failures trigger automated retry loops with max retry counts?
4. **Governance & Limits**:
   - Should budget caps be defined per profile, per tenant workspace, or globally?

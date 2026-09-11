---
name: task_decomposer
description: Analyzes high-level project goals, resolves ambiguity, decomposes objectives into atomic sub-tasks with dependency links, and assigns workloads to specialized agent department heads.
---

# Task Decomposer Skill

Used exclusively by the `orchestrator` (Chief of Staff) profile to transform unstructured or complex user goals into an ordered, executable dependency graph mapped to specialist agents.

## Core Workflow

### 1. Intake & Ambiguity Gate
- Inspect incoming user goals for missing constraints, API credentials, or unclear acceptance criteria.
- If requirements are ambiguous, invoke the `clarify` tool before dispatching downstream work.

### 2. Atomic Decomposition
- Break the objective into small, single-responsibility sub-tasks.
- Ensure each sub-task has:
  - `task_name`: Clear, imperative title (e.g., "Verify Token Expenditure").
  - `assigned_profile`: Targeted specialist profile.
  - `dependencies`: Prerequisite tasks that must complete first.
  - `deliverable`: Expected concrete output (code, report, email draft, documentation).

### 3. Department Head Mapping
Strictly map tasks according to organizational boundaries:

| Domain | Assigned Profile | Expected Deliverable |
| :--- | :--- | :--- |
| **Financial / Token Audit** | `cost_controller` | Token usage breakdown, budget cap compliance, `SpendReport`. |
| **Quality & Security Gate** | `qa_auditor` | AST syntax compilation, leak detection, `approved` or `changes_requested` verdict. |
| **Client Communications** | `comms_agent` | Milestone updates, email drafts, external stakeholder notifications. |
| **Security & Threat Audit** | `security_guard` | Zero-trust vulnerability scan, secret checks, and tenant isolation report. |
| **Parallel General Tasks** | Sub-Agent (`delegate`) | Ephemeral task execution spawned via Hermes `delegate` tool. |

### 4. Review Gating & Synthesis
- Deliverables produced by specialist agents or sub-agents must always be reviewed by `qa_auditor` before marking the overall project complete.
- Once approved, synthesize all deliverables into a clean, high-level executive report for the user.

## CLI Helper Script Usage

Execute directly via Python or within the agent session:

```bash
# Validate and format a decomposed task plan (Dry Run)
python /workspace/profiles/orchestrator/skills/task_decomposer/run.py --goal "Build payment gateway" --dry-run

# Submit decomposed tasks to Django AgentTask registry
python /workspace/profiles/orchestrator/skills/task_decomposer/run.py --plan-file /path/to/plan.json --submit
```

# Core Enterprise Agent Profiles

This directory contains version-controlled, declarative definitions for the 5 foundational agent profiles in the Hermes Agent runtime.

## Directory Structure

```
agent_service/profiles/
├── orchestrator/          # Chief of Staff / Intake & Kanban router
│   ├── SOUL.md            # Persona, operational principles & rules
│   ├── config.yaml        # Profile configuration overrides (toolsets, provider)
│   └── profile.yaml       # Role description and metadata for Kanban decomposition
├── cost_controller/       # Financial controller & budget monitor
│   ├── SOUL.md
│   ├── config.yaml
│   └── profile.yaml
├── qa_auditor/            # Quality assurance & compliance auditor
│   ├── SOUL.md
│   ├── config.yaml
│   └── profile.yaml
├── comms_agent/           # Client communications & meeting scheduler
│   ├── SOUL.md
│   ├── config.yaml
│   └── profile.yaml
└── archivist/             # Knowledge archivist & documentation maintainer
    ├── SOUL.md
    ├── config.yaml
    └── profile.yaml
```

## Profile Roles Summary

| Profile | Role Name | Primary Responsibility | Core Toolsets |
| :--- | :--- | :--- | :--- |
| `orchestrator` | Chief of Staff | Request intake, goal decomposition, Kanban dispatch | `kanban`, `delegate`, `terminal`, `file_ops`, `clarify` |
| `cost_controller` | Financial Controller | Token usage tracking, budget caps, expense auditing | `terminal`, `file_ops`, `web` |
| `qa_auditor` | QA & Compliance | Output validation, review gate, `request-changes` | `kanban`, `terminal`, `file_ops` |
| `comms_agent` | Client Coordinator | External messaging, email drafts, scheduling | `file_ops`, `terminal` |
| `archivist` | Knowledge Archivist | System documentation, wiki sync, SOP retrieval | `file_ops`, `terminal`, `web` |

## Provisioning
These definitions are synchronized into the running Hermes container (`/root/.hermes/profiles/<name>/`) via `scripts/provision_profiles.py`.

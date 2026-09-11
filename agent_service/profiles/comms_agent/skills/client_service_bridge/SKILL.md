---
name: client_service_bridge
description: Enterprise Client Portal concierge bridge for querying client tasks, document inventories, secure REST file streaming, budget milestone audits, and multi-channel notifications.
---

# Client Service Bridge Skill

Used by the `comms_agent` (Client Service & Communications Coordinator) to interact with external clients and the Django backend under strict zero-trust data scoping and engagement budget governance.

## Capabilities

1. **Engagement AI Budget & Milestone Audit**:
   - Evaluates client cumulative spend against allocated budget ($B$).
   - Returns milestone status (`OK`, `WARNING_75`, `EXCEEDED_100`) and tracks the 25%, 50%, 75%, and 100% threshold checkpoints.
   - Supports logging incremental spend deltas.
2. **Client Task & Checklist Status Query**:
   - Queries Django task registry filtered strictly by the client's scope.
   - Summarizes ongoing tasks, deliverables, and missing checklist items.
3. **Document Inventory & Secure REST Streaming**:
   - Queries client-scoped document catalogs in `apps.media`.
   - Streams authorized document files over authenticated HTTP with automatic local cleanup, preserving the zero-trust boundary (no shared media directory).
4. **Outbound Multi-Channel Notification Dispatch**:
   - Dispatches structured client updates across channels (`in_app`, `email`, `webhook`, `slack`) via `apps.notifications`.

## CLI Usage

```bash
# 1. Check client AI budget and milestone status
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode budget-check --client-id <CLIENT_ID> [--json]

# 2. Log spend delta consumed during a client interaction
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode budget-check --client-id <CLIENT_ID> --log-spend 0.0050

# 3. Inspect client-scoped engagement tasks and status
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode status --client-id <CLIENT_ID>

# 4. List client uploaded documents in apps.media
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode documents --client-id <CLIENT_ID>

# 5. Fetch a client document via secure REST stream
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode fetch-doc --doc-id <DOC_UUID> --output-file /workspace/scratch/client_file.pdf

# 6. Dispatch outbound notification to client / staff
python /workspace/profiles/comms_agent/skills/client_service_bridge/run.py --mode notify --title "Audit Update" --message "Q2 financial review completed." --channel email
```

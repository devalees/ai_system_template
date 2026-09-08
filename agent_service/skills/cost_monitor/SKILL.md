---
name: cost_monitor
description: Audits LLM token consumption and estimated API costs from Hermes session logs, evaluating spend against budget limits.
---

# Cost Monitor Skill

Used by the `cost_controller` agent to monitor token consumption, calculate expenditure across models, and enforce budget thresholds.

## Capabilities
1. Scans active and recent Hermes session transcripts in `/root/.hermes/sessions/`.
2. Computes total prompt tokens, completion tokens, and model distribution.
3. Calculates estimated dollar costs using reference model pricing.
4. Checks current spend against defined budget caps ($/day or $/project).
5. Emits structured JSON metrics and an executive variance summary.

## Usage
Execute directly via Python or within the agent session:
```bash
python /workspace/skills/cost_monitor/run.py [--daily-budget 10.00] [--json]
```

---
name: django_handshake
description: Pings the Django backend to register the Hermes Agent session and establish bidirectional API connectivity.
---

# Django Handshake Skill

This skill enables Hermes Agent to:
1. Probe the Django backend health endpoint (`GET /api/health/`).
2. Submit an agent handshake payload (`POST /api/handshake/`).
3. Confirm that the handshake is recorded in the PostgreSQL database.

## Usage
Executed by the agent daemon or directly via Python:
```bash
python /workspace/skills/django_handshake/run.py
```

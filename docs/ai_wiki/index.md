# AI System Template — System Overview

An extensible, production-ready starter template pairing a **Django** web framework (REST API, Admin, PostgreSQL, Redis) with the autonomous **Nous Research Hermes Agent** execution environment in Docker.

- **Repository**: `devalees/ai_system_template`
- **Active Implementation Plan**: [`docs/plans/active_plan.md`](file:///home/ehab/Desktop/economy_editor/docs/plans/active_plan.md)
- **Status**: Initialization & Scaffolding

---

## Primary System Components

1. **Backend Service (`backend/`)**:
   - Python 3.11 / 3.12 with Django 5 & Django REST Framework.
   - PostgreSQL as relational database.
   - Redis for caching, session storage, and event queuing.
   - Provides administrative UI (`/admin`) and REST API endpoints for agent management, health monitoring, and data ingestion.

2. **Hermes Agent Runtime (`agent_service/` & Docker)**:
   - Powered by `hermes-agent` (Nous Research autonomous agent engine).
   - Runs as a decoupled service with access to local skills and storage.
   - Communicates with Django via REST endpoints and webhooks.

3. **Bidirectional Integration & Handshake**:
   - Standardized API contract enabling Hermes to register its state, receive tasks, and report results to Django.
   - Automated handshake verification testing connectivity between containers.

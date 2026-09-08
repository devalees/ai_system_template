# System Architecture: AI System Template

## 1. Technical Stack

* **Backend Web Framework**: Django 5.x + Django REST Framework (Python 3.11/3.12)
* **Agent Engine**: Hermes Agent (`hermes-agent:local` / `NousResearch/hermes-agent`)
* **Primary Database**: PostgreSQL 16
* **Cache & Broker**: Redis 7
* **Container Orchestration**: Docker & Docker Compose
* **API Paradigm**: REST + JSON Webhooks

---

## 2. Container Network & Ports

| Service | Internal Port | Host Port | Purpose |
| :--- | :--- | :--- | :--- |
| `postgres` | 5432 | 5432 (or configurable) | Relational data persistence for Django |
| `redis` | 6379 | 6379 (or configurable) | Fast cache & event broker |
| `backend` | 8000 | 8000 | Django REST API & Admin Portal |
| `hermes` | 8642 | 8642 | Hermes Agent Gateway & API |
| `hermes-dashboard` | 9119 | 9119 | Hermes Web UI / Inspection Dashboard |

---

## 3. Communication Patterns

### Django to Hermes (Orchestration & Triggers)
* Django dispatches tasks or triggers to Hermes via Hermes's HTTP Gateway (`http://hermes:8642/...`).
* Can pass execution context, parameters, and callback endpoints.

### Hermes to Django (Handshake & Data Ingestion)
* Hermes runs skills or Python scripts that call Django's REST endpoints (`http://backend:8000/api/...`).
* Submits telemetry, status updates, agent run logs, or generated domain artifacts.

---

## 4. Directory Structure

```
ai_system_template/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── docs/
│   ├── ai_wiki/
│   │   ├── index.md
│   │   └── architecture.md
│   └── plans/
│       └── active_plan.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── core/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── apps/
│       └── integration/
│           ├── models.py
│           ├── views.py
│           ├── serializers.py
│           ├── urls.py
│           └── admin.py
├── agent_service/
│   ├── Dockerfile
│   ├── config/
│   │   └── config.yaml
│   └── skills/
│       └── handshake/
│           ├── SKILL.md
│           └── run.py
└── scripts/
    └── test_handshake.sh
```

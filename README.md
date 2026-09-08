# AI System Template (Decoupled Django & Hermes Agent)

[![Docker](https://img.shields.io/badge/Docker-Isolated_Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-5.0+-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Hermes Agent](https://img.shields.io/badge/Nous-Hermes_Agent-purple)](https://github.com/NousResearch/hermes-agent)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

A production-ready, domain-agnostic starter template pairing a **Django** backend service with an autonomous **Nous Research Hermes Agent** runtime, deployed in **two separate, isolated Docker environments** for security.

Neither container shares internal networks or storage; all communication flows strictly through authenticated REST API endpoints over HTTP.

---

## Architectural Blueprint

```
 ┌──────────────────────────────────────────────┐
 │               Host Machine                   │
 │                                              │
 │  ┌────────────────────────────────────────┐  │
 │  │ Docker Environment 1: Django Backend   │  │
 │  │ (backend/docker-compose.yml)           │  │
 │  │  - Django REST API & Admin (Port 8000) │  │
 │  │  - PostgreSQL 16 (Port 5432)           │  │
 │  │  - Redis 7 (Port 6379)                 │  │
 │  └────────────────────▲───────────────────┘  │
 │                       │                      │
 │          REST API     │                      │
 │          HTTP Traffic │                      │
 │                       │                      │
 │  ┌────────────────────▼───────────────────┐  │
 │  │ Docker Environment 2: Hermes Agent     │  │
 │  │ (agent_service/docker-compose.yml)     │  │
 │  │  - Hermes Agent Daemon (Port 8643)     │  │
 │  │  - Autonomous Skills & Local Storage   │  │
 │  └────────────────────────────────────────┘  │
 └──────────────────────────────────────────────┘
```

---

## Quickstart Guide

### 1. Start Django Backend (Environment 1)
```bash
cd backend
cp .env.example .env
docker compose up -d --build
```
* Django Admin available at: `http://localhost:8000/admin/` (default credentials: `admin` / `admin12345`)
* API Health endpoint: `http://localhost:8000/api/health/`

### 2. Start Hermes Agent (Environment 2)
```bash
cd ../agent_service
cp .env.example .env
docker compose up -d
```
* Hermes Gateway available at: `http://localhost:8643/`

### 3. Run Bidirectional Handshake Verification
From the root directory:
```bash
python scripts/verify_handshake.py
```
Or execute the handshake skill directly inside the Hermes container:
```bash
docker compose -f agent_service/docker-compose.yml exec hermes python /workspace/skills/django_handshake/run.py
```

---

## Directory Structure

```
├── docs/
│   ├── ai_wiki/             # Architecture and system documentation
│   └── plans/               # Active implementation plan & task state
├── backend/                 # Isolated Docker Project 1 (Django)
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── core/
│   └── apps/integration/
├── agent_service/           # Isolated Docker Project 2 (Hermes)
│   ├── docker-compose.yml
│   ├── .env.example
│   └── skills/django_handshake/
└── scripts/
    └── verify_handshake.py  # Verification script
```

---

## License
MIT

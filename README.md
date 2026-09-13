# Sovereign Autonomous AI Agent Platform

[![Docker](https://img.shields.io/badge/Docker-Isolated_Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Hermes Agent](https://img.shields.io/badge/Nous-Hermes_Agent-purple)](https://github.com/NousResearch/hermes-agent)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Standardized_Tools-00D26A)](https://modelcontextprotocol.io/)
[![sqlite-vec](https://img.shields.io/badge/sqlite--vec-In--Process_Vector_DB-orange)](https://github.com/asg017/sqlite-vec)
[![Langfuse](https://img.shields.io/badge/Langfuse-LLMOps_Tracing-blue)](https://langfuse.com/)

A production-grade, 100% sovereign, and portable autonomous AI agent platform powered by the **Nous Research Hermes Agent** execution engine. Completely independent, containerized, and decoupled from any external web frameworks or databases.

---

## The 6 Sovereign Pillars

1. **Embedded Sovereign Semantic Memory (`sqlite-vec`)**: In-process vector database inside `agent_service/data/memory.db`. Zero network latency, sub-15ms cosine distance recall, and 100% portable with the agent runtime.
2. **Model Context Protocol (FastMCP) Standardized Tooling**: Internal JSON-RPC tool ecosystem (`agent_service/mcp/`) replacing fragile shell scripts with typed, high-speed tools.
3. **Glass-Box Observability & Tracing (Langfuse)**: Standalone Docker monitoring service on port `3100` capturing complete thought streams, tool execution waterfalls, latency, and token costs.
4. **Schema-Strict Self-Correction & Circuit Breakers**: Pydantic input/output contracts, mid-flight traceback injection for self-healing, and anti-loop circuit breakers.
5. **Independent Golden Benchmark Evaluation Suite (`agent_service/evals/`)**: Automated `pytest` test harness certifying agent intelligence standalone with deterministic domain scenarios.
6. **Cross-Project Knowledge Portability**: Self-contained package architecture with sanitized knowledge export/import CLI (`agent_service/memory/cli.py`) for compound intelligence across projects.

---

## Directory Architecture

```
economy_editor/
├── agent_service/                   # Sovereign AI Agent Package (100% Portable)
│   ├── docker-compose.yml           # Hermes isolated container definition
│   ├── profiles/                    # Calibrated Profiles (SOUL.md, config.yaml)
│   ├── mcp/                         # Internal Model Context Protocol Tool Ecosystem
│   │   ├── system_tools_server.py   # FastMCP server exposing tools over JSON-RPC
│   │   └── schemas/                 # Pydantic input/output validation schemas
│   ├── memory/                      # Embedded Sovereign Vector Engine (sqlite-vec)
│   │   ├── vector_store.py          # Vector store with cosine similarity search (<15ms)
│   │   └── cli.py                   # Knowledge Export & Import CLI (PII-sanitized)
│   ├── data/                        # Persistent storage (memory.db, runtime state)
│   ├── evals/                       # Independent Golden Benchmark Evaluation Suite
│   │   └── test_golden_evals.py     # Deterministic domain scenarios (pytest)
│   └── telemetry/                   # Glass-Box Observability Hooks (Langfuse / OTel)
└── docs/
    ├── ai_wiki/                     # System architecture & documentation wiki
    └── plans/                       # Implementation plans & active roadmap
```

---

## Quickstart Guide

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and supply your LLM provider API keys (OpenRouter, Gemini, Groq, Anthropic, or OpenAI)
```

### 2. Launch Standalone Agent Service
```bash
docker compose -f agent_service/docker-compose.yml up -d
```

### 3. Verify Hermes Gateway
```bash
# Check loaded models via OpenAI-compatible Gateway API
curl -H "Authorization: Bearer hermes_agent_secret_key_prod_2026_audit" http://localhost:8643/v1/models
```

### 4. Interactive CLI Execution
```bash
docker exec -it hermes-template-agent hermes chat
```

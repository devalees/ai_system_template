# Sovereign Autonomous Agent Platform (`agent_service/`)

A 100% sovereign, portable, standalone AI agent platform powered by embedded in-process semantic memory (`sqlite-vec`), native FastMCP tools, and glass-box LLMOps tracing.

---

## 1. Architectural Highlights

1. **Embedded Sovereign Vector Memory (`sqlite-vec`)**:
   - In-process vector database in `data/memory.db`.
   - Deterministic dense feature embeddings ($<1\text{ ms}$).
   - Sub-15ms cosine similarity recall with zero external database dependencies.
2. **Model Context Protocol (FastMCP)**:
   - Native in-process JSON-RPC 2.0 tool execution (`mcp/system_tools_server.py`).
   - Rigid Pydantic validation contracts (`mcp/schemas.py`).
3. **Glass-Box Tracing & LLMOps (Langfuse :3100)**:
   - Visual trace waterfalls, generation spans, thinking reasoning streams, and real-time token spend accounting (`telemetry/tracer.py`).
4. **Tiered Risk-Based QA State Machine**:
   - Tier 1: Deterministic AST syntax verification ($0 token spend, <5ms).
   - Tier 2: Mid-flight traceback reflection with actionable line numbers.
   - Tier 3: Conditional escalation for high-risk deliverables.
   - Anti-loop circuit breaker terminating repeated tool failures.
5. **Independent Golden Benchmark Suite**:
   - 43 deterministic evaluation tests in `evals/` running in <3s with 100% pass rate.
6. **Cross-Project Portability**:
   - Knowledge export/import CLI (`memory/cli.py`) with automated PII and secret redaction.

---

## 2. Quick Start

### Running with Docker Compose
```bash
# Start Hermes Agent Gateway (:8643), Langfuse Dashboard (:3100), and PostgreSQL (:5432)
docker compose up -d

# Verify Gateway health
curl -s http://localhost:8643/v1/models

# Verify Langfuse health
curl -s http://localhost:3100/api/public/health
```

### Running the Golden Benchmark Suite
```bash
./evals/run_evals.sh
```

### Managing Knowledge Memory (CLI)
```bash
# View memory store statistics
python3 -m memory.cli stats

# Semantic query against memory embeddings
python3 -m memory.cli query "how to resolve permission denied in docker"

# Export sanitized generalized knowledge
python3 -m memory.cli export --scope generalized --output knowledge_export.jsonl

# Import knowledge into new environment
python3 -m memory.cli import --input knowledge_export.jsonl
```

---

## 3. Autonomous Workforce

| Profile | Role | Reasoning Budget | Dedicated FastMCP Tool |
| :--- | :--- | :--- | :--- |
| **`orchestrator`** | Chief of Staff & DAG Planner | `none` (0s triage) | `decompose_task_dag`, `discover_external_system` |
| **`cost_controller`** | Financial Controller & Token Spend Auditor | `low` | `audit_token_budget` |
| **`qa_auditor`** | Compliance & Quality Gatekeeper | `high` | `validate_code_deliverable` |
| **`security_guard`** | SecOps & Threat Auditor | `high` | `security_audit` |
| **Dynamic Specialists** | Custom Domain Specialists (e.g. Procurement, Radiology) | Calibrated | `invoke_external_api`, `sync_external_records` |


# Sovereign Headless Backend Platform

A high-performance asynchronous micro-kernel backend platform powered by FastAPI, SQLAlchemy 2.0 Async (`asyncpg`), PostgreSQL 16, Redis 7, and Celery.

## Features
- **Micro-Kernel Architecture**: Dynamic module discovery with acyclic DAG validation.
- **Native Multi-Tenancy**: Kernel-enforced `company_id` isolation.
- **Universal Query Engine**: Declarative AST query compiler with support for nested boolean filters and aggregations.
- **AI Agent Integration**: Direct bridge to Nous Hermes Agent (`agent_service/`) and FastMCP reflection.

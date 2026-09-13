# FastAPI Development & API Synchronization Standards

Guidelines and rules governing FastAPI development, schema integrity, and client testing synchronization.

---

## 1. Continuous OpenAPI & Postman Synchronization Protocol (Mandatory)

To guarantee that API consumers, QA engineers, and Postman test collections never fall out of sync with backend code:

### A. Comprehensive Endpoint Documentation & Typing
* **Strict Pydantic Contracts**: Every endpoint MUST define explicit `response_model`, `status_code`, and strongly typed request bodies/parameters. No untyped dictionaries or raw JSON bodies.
* **Metadata & Grouping**: Every endpoint MUST declare:
  * `tags`: Grouped cleanly by module (e.g. `["Sales"]`, `["Audit"]`, `["Auth"]`).
  * `summary`: Concise one-line description of the operation.
  * `description`: Detailed markdown explaining behavior, business rules, and permissions.
  * `responses`: Error response schemas (400, 401, 403, 404, 422).

### B. Automated Schema Export on Every API Change
* Whenever a task or sub-task adds, modifies, or deprecates an API endpoint, model, or parameter:
  1. The agent MUST generate and update the static OpenAPI specification file located at:
     [`docs/api/openapi.json`](file:///home/ehab/Desktop/economy_editor/docs/api/openapi.json)
  2. The export MUST represent 100% of all registered routes across the Kernel, Base Utilities, and Pluggable Modules.
  3. The agent must verify that the exported JSON is valid and can be imported directly into **Postman** or **Swagger UI** with zero missing URLs or broken parameter references.

### C. Atomic Git Synchronization
* The updated `docs/api/openapi.json` must be committed to Git alongside the code changes in the same atomic commit.

---

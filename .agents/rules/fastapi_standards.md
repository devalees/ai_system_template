# FastAPI Development & API Synchronization Standards

Guidelines and rules governing FastAPI development, schema integrity, client testing synchronization, and AI-agent consumable documentation.

---

## 1. Continuous OpenAPI & Postman Synchronization Protocol (Mandatory)

To guarantee that API consumers, QA engineers, and Postman test collections never fall out of sync with backend code:

### A. Strict Endpoint Contracts & Grouping
* **Explicit Pydantic Types**: Every endpoint MUST define explicit `response_model`, HTTP `status_code`, and strongly typed request bodies and parameters. No untyped dictionaries (`dict`), unstructured `Any`, or raw JSON requests/responses.
* **Metadata & Grouping**: Every endpoint MUST declare:
  * `tags`: Grouped cleanly by domain module (e.g. `["Sales"]`, `["Audit"]`, `["Auth"]`, `["Settings"]`).
  * `summary`: Concise one-line action title (e.g., `"Confirm and Post Sales Invoice"`).
  * `description`: In-depth markdown documentation explaining preconditions, side effects, and permissions (see Section 2).
  * `responses`: Explicit error schemas and example bodies for `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, and `422 Unprocessable Entity`.

### B. Automated Schema & Postman Artifact Export on Every API Change
Whenever any task or sub-task adds, modifies, or deprecates an endpoint, data model, or parameter:
1. The agent MUST regenerate and update the static OpenAPI specification file located at:
   [`docs/api/openapi.json`](file:///home/ehab/Desktop/economy_editor/docs/api/openapi.json)
2. The agent MUST generate/update the companion **Postman Collection v2.1** and **Postman Environment** files:
   * Collection: [`docs/api/postman_collection.json`](file:///home/ehab/Desktop/economy_editor/docs/api/postman_collection.json)
   * Environment: [`docs/api/postman_environment.json`](file:///home/ehab/Desktop/economy_editor/docs/api/postman_environment.json)
3. The export MUST represent 100% of all registered routes across the Kernel, Base Utilities, and Pluggable Modules.
4. The agent must verify that the exported files can be imported directly into **Postman** with zero missing URLs or broken parameter references.

---

## 2. Agent-First API Documentation Standards (LLM & MCP Precision)

Because API documentation is ingested directly by **AI Agents (Hermes Agent, FastMCP reflection engines)** as well as human developers, documentation must be machine-actionable:

* **Preconditions & State Transitions**:
  * Explicitly state what record states are required before invoking the endpoint (e.g., *"Invoice must be in 'draft' state; calling on 'posted' invoice returns 400"*).
* **Validation Constraints**:
  * Document all field boundary rules (min/max numeric bounds, regex patterns, enum choices, required relational IDs).
* **Realistic Example Payloads**:
  * Every endpoint must provide realistic, semantically valid example request and response JSON payloads in Pydantic `model_config = ConfigDict(json_schema_extra={...})`. Never use placeholder text like `{"foo": "bar"}` or `{"string": "string"}`.
* **Actionable Error Explanations**:
  * In error responses, provide actionable hints so an autonomous AI agent can self-correct its payload mid-flight if it encounters a 400 or 422 error.

---

## 3. Automated Postman Environment & Dynamic Token Inheritance

To eliminate the manual friction of copying and pasting tokens or configuring environments:

### A. Standardized Postman Environment (`docs/api/postman_environment.json`)
The exported environment must come pre-configured with:
* `base_url`: Defaulted to `http://localhost:8000` (or Docker port mapping).
* `auth_token`: Initially empty, dynamically populated upon login.
* `active_company_id`: Default multi-tenant company ID.
* `current_user_id`: Populated dynamically.

### B. Automatic Post-Login Token Capture Script
* In the Postman Collection, the `POST /api/v1/auth/login` (and token refresh) request MUST include a standardized post-response test script:
  ```javascript
  if (pm.response.code === 200) {
      var json = pm.response.json();
      if (json.access_token) {
          pm.environment.set("auth_token", json.access_token);
      }
      if (json.company_id) {
          pm.environment.set("active_company_id", json.company_id);
      }
  }
  ```

### C. Collection-Level Authorization Inheritance
* Every folder and request in the Postman Collection inherits authorization from the root:
  * Type: `Bearer Token`
  * Token: `{{auth_token}}`
* Multi-tenant header injection: Every request automatically includes `X-Company-ID: {{active_company_id}}`.
* **Zero-Friction Workflow**: The developer or QA engineer logs in once; all subsequent requests in the collection authenticate and route automatically without manual token copying.

---

## 4. Atomic Git Synchronization

* The updated `docs/api/openapi.json`, `docs/api/postman_collection.json`, and `docs/api/postman_environment.json` must be committed to Git alongside the corresponding backend code changes in the same atomic commit.

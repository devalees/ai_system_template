---
name: security_scanner
description: Multi-mode SecOps scanner for secret leak detection, multi-tenant isolation verification, RBAC permission auditing, and API gateway threat monitoring.
---

# Security Scanner Skill

Used by the `security_guard` profile to enforce Zero-Trust defense, audit codebases and deliverables for leaked secrets, verify multi-tenant isolation, audit service account permissions, and monitor gateway threat logs.

## Capabilities
1. **`secrets-scan`**:
   - Recursively inspects files and directories for unmasked secrets:
     - OpenAI API keys (`sk-...`)
     - OpenRouter API keys (`sk-or-...`)
     - Anthropic API keys (`sk-ant-...`)
     - Stripe live & test keys (`sk_live_...`, `rk_live_...`)
     - Generic API tokens, private RSA/SSH keys, passwords, and `.env` files.
   - Assigns severity ratings: `CRITICAL`, `HIGH`, `MEDIUM`.
2. **`tenant-audit`**:
   - Inspects Django models across `backend/apps/` to verify that business entities inherit `TenantAwareModel`.
   - Flags unisolated queries or missing organization scoping.
3. **`rbac-audit`**:
   - Connects to Django REST backend using `bot_security_guard`'s credentials.
   - Audits service accounts (`bot_*`) to verify they strictly adhere to the Principle of Least Privilege.
4. **`gateway-audit`**:
   - Queries Django REST endpoints for recent `WebhookEvent` and `ActivityLog` telemetry.
   - Identifies failed HMAC signatures, replay attempts, and authentication brute-force spikes.
5. **Structured JSON Output**:
   - Supports `--json` for pipeline integration and automated reporting.

## Usage
```bash
# Scan a directory or file for secret leaks
python run.py --mode secrets-scan --path /workspace/path/to/target

# Perform a multi-tenant model isolation audit
python run.py --mode tenant-audit --path /workspace/backend

# Perform a service account RBAC boundary audit
python run.py --mode rbac-audit

# Perform an API gateway threat audit
python run.py --mode gateway-audit

# Output structured JSON
python run.py --mode secrets-scan --path /workspace/backend --json
```

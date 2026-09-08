# System Architecture: Decoupled AI System Template

## 1. Technical Stack & Security Isolation

* **Backend Web Framework**: Django 5.x + Django REST Framework (Python 3.11)
* **Agent Engine**: Hermes Agent (`hermes-agent:local` / Nous Research)
* **Database**: PostgreSQL 16
* **Cache & Broker**: Redis 7
* **Container Architecture**: **Two Isolated Docker Projects**
  1. `backend/docker-compose.yml`: Encapsulates Django, PostgreSQL, and Redis in an internal network (`backend_network`).
  2. `agent_service/docker-compose.yml`: Encapsulates Hermes Agent in an isolated network (`hermes_isolated_network`).
* **Inter-Service Communication**: Strictly over HTTP REST API (`http://host.docker.internal:8000/api`) with zero shared container networks, storage, or privileges.

---

## 2. Port Allocation

| Service | Environment | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| `backend` | Django Project | 8000 | 8000 | Django REST API & Admin Portal |
| `db` | Django Project | 5432 | 5432 | PostgreSQL 16 |
| `redis` | Django Project | 6379 | 6379 | Redis 7 |
| `hermes` | Hermes Project | 8643 | 8642 | Hermes Agent Gateway daemon |

---

## 3. Communication Contract & Handshake

### Agent to Django
* `POST /api/handshake/`: Hermes transmits its agent ID, version, and metadata.
* Django logs the payload in `HandshakeLog` in PostgreSQL and returns an acknowledgment containing a `log_id` and server timestamp.

### Django to Agent
* `GET /api/ping-hermes/`: Django verifies reverse reachability to Hermes Gateway daemon via `HERMES_GATEWAY_URL`.

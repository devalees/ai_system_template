"""
Thread-safe and task-safe Audit Request Context Management.

Utilizes Python 3.11 `contextvars` to track client telemetry (IP address,
User-Agent, request correlation ID, and actor) across the request/task lifecycle
without cross-thread or cross-task leakage.
"""

import contextvars
from contextlib import contextmanager
from typing import Any, Dict, Optional

_client_ip_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("audit_client_ip", default=None)
_user_agent_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("audit_user_agent", default="")
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("audit_request_id", default="")
_audit_actor_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar("audit_actor", default=None)
_audit_metadata_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("audit_metadata", default=None)


def get_audit_ip() -> Optional[str]:
    """Retrieve client IP address from context."""
    return _client_ip_ctx.get()


def set_audit_ip(ip: Optional[str]):
    """Set client IP address in context."""
    return _client_ip_ctx.set(ip)


def get_audit_user_agent() -> str:
    """Retrieve client User-Agent string from context."""
    return _user_agent_ctx.get()


def set_audit_user_agent(user_agent: str):
    """Set client User-Agent string in context."""
    return _user_agent_ctx.set(user_agent or "")


def get_audit_request_id() -> str:
    """Retrieve request correlation ID from context."""
    return _request_id_ctx.get()


def set_audit_request_id(request_id: str):
    """Set request correlation ID in context."""
    return _request_id_ctx.set(request_id or "")


def get_audit_actor() -> Any:
    """Retrieve explicit audit actor override from context."""
    return _audit_actor_ctx.get()


def set_audit_actor(actor: Any):
    """Set explicit audit actor override in context."""
    return _audit_actor_ctx.set(actor)


def get_audit_metadata() -> Dict[str, Any]:
    """Retrieve context metadata dictionary."""
    meta = _audit_metadata_ctx.get()
    return dict(meta) if meta else {}


def set_audit_metadata(metadata: Optional[Dict[str, Any]]):
    """Set context metadata dictionary in context."""
    return _audit_metadata_ctx.set(metadata)


def clear_audit_context():
    """Reset all audit context variables to their default values."""
    _client_ip_ctx.set(None)
    _user_agent_ctx.set("")
    _request_id_ctx.set("")
    _audit_actor_ctx.set(None)
    _audit_metadata_ctx.set(None)


@contextmanager
def audit_context(
    actor: Any = None,
    ip: Optional[str] = None,
    user_agent: str = "",
    request_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for scoping audit context within background jobs,
    celery tasks, or testing blocks.

    Example:
        with audit_context(actor=system_bot, ip="10.0.0.1", request_id="req-999"):
            entity.save()  # Audit trail captures these parameters
    """
    t_actor = _audit_actor_ctx.set(actor)
    t_ip = _client_ip_ctx.set(ip)
    t_ua = _user_agent_ctx.set(user_agent or "")
    t_req = _request_id_ctx.set(request_id or "")
    t_meta = _audit_metadata_ctx.set(metadata)
    try:
        yield
    finally:
        _audit_actor_ctx.reset(t_actor)
        _client_ip_ctx.reset(t_ip)
        _user_agent_ctx.reset(t_ua)
        _request_id_ctx.reset(t_req)
        _audit_metadata_ctx.reset(t_meta)

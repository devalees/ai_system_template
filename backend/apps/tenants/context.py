"""
Thread-safe and task-safe Tenant Context Management.

Utilizes Python 3.11 `contextvars` to manage the active Organization
in the request/task execution lifecycle without thread-local leakage.
"""

import contextvars
from contextlib import contextmanager
from typing import Optional

_current_tenant_ctx = contextvars.ContextVar("current_tenant", default=None)
_bypass_tenant_isolation_ctx = contextvars.ContextVar("bypass_tenant_isolation", default=False)


def get_current_tenant():
    """
    Retrieve the current active Organization from the context.

    Returns:
        Organization instance or None if outside a tenant context.
    """
    return _current_tenant_ctx.get()


def set_current_tenant(organization):
    """
    Directly set the active Organization in the context.

    Returns:
        Token that can be used to reset the context.
    """
    return _current_tenant_ctx.set(organization)


def clear_current_tenant(token=None):
    """
    Clear the current tenant context. If a token is provided, resets to previous state.
    """
    if token:
        _current_tenant_ctx.reset(token)
    else:
        _current_tenant_ctx.set(None)


def is_tenant_isolation_bypassed() -> bool:
    """
    Check if tenant isolation is globally bypassed for the current task/request.
    """
    return _bypass_tenant_isolation_ctx.get()


@contextmanager
def tenant_context(organization):
    """
    Context manager to execute code within a specific tenant context.

    Example:
        with tenant_context(org):
            records = DynamicEntity.objects.all()  # Scoped to org
    """
    token = _current_tenant_ctx.set(organization)
    try:
        yield organization
    finally:
        _current_tenant_ctx.reset(token)


@contextmanager
def bypass_tenant_isolation():
    """
    Context manager to temporarily bypass tenant isolation (e.g., for migrations,
    cross-tenant analytics, or superuser maintenance tasks).

    Example:
        with bypass_tenant_isolation():
            all_records = DynamicEntity.objects.all()  # Unfiltered
    """
    token = _bypass_tenant_isolation_ctx.set(True)
    try:
        yield
    finally:
        _bypass_tenant_isolation_ctx.reset(token)

"""
Request Context & Current User Middleware.

Utilizes Python 3.11's standard library `contextvars` to provide a thread-safe,
async-safe thread-local alternative for capturing the active request and user
across model lifecycle hooks (e.g. `AuditableModel.save`).
"""

import contextvars
from typing import Optional
from django.contrib.auth.models import AnonymousUser

# Thread-safe and task-safe context variable holding the authenticated or anonymous user
_current_user_ctx = contextvars.ContextVar("current_user", default=None)


def get_current_user():
    """
    Retrieve the current user from the active request context.

    Returns:
        User model instance, AnonymousUser, or None if outside request lifecycle.
    """
    return _current_user_ctx.get()


def get_current_authenticated_user():
    """
    Retrieve the current authenticated user from the active request context.

    Returns:
        Authenticated User instance, or None if user is unauthenticated/outside request.
    """
    user = _current_user_ctx.get()
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


class CurrentUserMiddleware:
    """
    Middleware capturing the active `request.user` into a context variable.

    Guarantees clean lifecycle cleanup via context token reset in a `finally` block
    to prevent memory retention or user state leakage across concurrent worker threads.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        token = _current_user_ctx.set(user)
        try:
            response = self.get_response(request)
            return response
        finally:
            _current_user_ctx.reset(token)

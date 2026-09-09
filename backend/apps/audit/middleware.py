"""
Audit Context & Telemetry Middleware.

Captures client IP address, User-Agent, and request correlation ID (X-Request-ID),
binding them to task-safe `contextvars` for automatic attribution in model signals
and audit records. Injects `X-Request-ID` into response headers.
"""

import uuid
from typing import Optional

from apps.audit.context import (
    _audit_actor_ctx,
    _client_ip_ctx,
    _request_id_ctx,
    _user_agent_ctx,
)


class AuditContextMiddleware:
    """
    Captures incoming client telemetry and injects correlation IDs into the request lifecycle.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip_address = self.extract_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        request_id = (
            request.META.get("HTTP_X_REQUEST_ID")
            or request.META.get("HTTP_X_CORRELATION_ID")
            or f"req_{uuid.uuid4().hex[:16]}"
        )

        # Attach request ID to request object for easy logging and inspection
        request.id = request_id
        request.client_ip = ip_address

        # Resolve actor (if user is authenticated)
        user = getattr(request, "user", None)
        actor = user if (user and getattr(user, "is_authenticated", False)) else None

        # Bind to contextvars
        t_ip = _client_ip_ctx.set(ip_address)
        t_ua = _user_agent_ctx.set(user_agent)
        t_req = _request_id_ctx.set(request_id)
        t_actor = _audit_actor_ctx.set(actor)

        try:
            response = self.get_response(request)
            if response is not None and not response.has_header("X-Request-ID"):
                response["X-Request-ID"] = request_id
            return response
        finally:
            _client_ip_ctx.reset(t_ip)
            _user_agent_ctx.reset(t_ua)
            _request_id_ctx.reset(t_req)
            _audit_actor_ctx.reset(t_actor)

    @staticmethod
    def extract_client_ip(request) -> Optional[str]:
        """
        Extract the actual client IP address handling proxies and CDNs.
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # First IP in comma-separated list is the originating client
            ip = x_forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return x_real_ip.strip()

        remote_addr = request.META.get("REMOTE_ADDR")
        if remote_addr:
            return remote_addr.strip()

        return None

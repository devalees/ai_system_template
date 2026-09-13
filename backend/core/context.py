"""Thread-safe request context management and multi-tenancy middleware."""

import uuid
from contextvars import ContextVar
from typing import Optional, Callable, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from core.config import settings

# Thread-safe context variables for async request lifecycle
_active_company_id: ContextVar[Optional[uuid.UUID]] = ContextVar("active_company_id", default=None)
_current_user_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_user_id", default=None)
_actor_type: ContextVar[str] = ContextVar("actor_type", default="anonymous")


def get_active_company_id() -> Optional[uuid.UUID]:
    """Retrieve the currently active tenant company ID from context."""
    return _active_company_id.get()


def set_active_company_id(company_id: Optional[uuid.UUID]) -> None:
    """Set the active tenant company ID in context."""
    _active_company_id.set(company_id)


def get_current_user_id() -> Optional[uuid.UUID]:
    """Retrieve the authenticated user or agent ID from context."""
    return _current_user_id.get()


def set_current_user_id(user_id: Optional[uuid.UUID]) -> None:
    """Set the current user ID in context."""
    _current_user_id.set(user_id)


def get_actor_type() -> str:
    """Retrieve the current actor type ('human', 'ai_agent', 'system', 'anonymous')."""
    return _actor_type.get()


def set_actor_type(actor_type: str) -> None:
    """Set the actor type in context."""
    _actor_type.set(actor_type)


class MultiTenancyContextMiddleware(BaseHTTPMiddleware):
    """Middleware extracting tenant company ID and actor identity from HTTP headers and JWT tokens."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        token_company = None
        token_user = None
        token_actor = None

        # 1. Parse JWT Bearer Authorization header if present
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
            try:
                payload = jwt.decode(
                    raw_token,
                    settings.JWT_SECRET_KEY,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                if "sub" in payload:
                    token_user = _safe_parse_uuid(payload["sub"])
                if "company_id" in payload:
                    token_company = _safe_parse_uuid(payload["company_id"])
                if "actor_type" in payload:
                    token_actor = str(payload["actor_type"])
                elif "user_type" in payload:
                    token_actor = str(payload["user_type"])
            except JWTError:
                # Token decode failure is handled downstream by auth dependencies
                pass

        # 2. Extract X-Company-ID header (overrides token if specified or for tenant switching)
        company_header = request.headers.get("X-Company-ID")
        if company_header:
            parsed_company = _safe_parse_uuid(company_header)
            if parsed_company:
                token_company = parsed_company

        # 3. Extract X-Actor-Type header if provided (e.g. from internal services/FastMCP)
        actor_header = request.headers.get("X-Actor-Type")
        if actor_header:
            token_actor = actor_header

        # 4. Set ContextVar tokens and ensure cleanup after request
        company_token = _active_company_id.set(token_company)
        user_token = _current_user_id.set(token_user)
        actor_token = _actor_type.set(token_actor or "anonymous")

        try:
            response = await call_next(request)
            return response
        finally:
            _active_company_id.reset(company_token)
            _current_user_id.reset(user_token)
            _actor_type.reset(actor_token)


def _safe_parse_uuid(val: Any) -> Optional[uuid.UUID]:
    """Safely convert string or integer representation into UUID."""
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None

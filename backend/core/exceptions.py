"""Standard error envelope classes and platform exceptions."""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime, timezone


class PlatformException(Exception):
    """Base exception for all Sovereign Platform domain and kernel errors."""

    def __init__(
        self,
        code: str,
        message: str,
        resolution_hint: str = "",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.resolution_hint = resolution_hint
        self.details = details or {}
        self.status_code = status_code

    def to_envelope(self) -> Dict[str, Any]:
        """Convert exception to standardized machine-actionable JSON envelope."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "resolution_hint": self.resolution_hint,
                "details": self.details,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class EntityNotFoundException(PlatformException):
    """Raised when a requested database entity does not exist."""

    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            code="ENTITY_NOT_FOUND",
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            resolution_hint=f"Verify the '{entity_name}' identifier and ensure you have tenant access.",
            details={"entity": entity_name, "identifier": str(identifier)},
            status_code=status.HTTP_404_NOT_FOUND,
        )


class NotFoundException(PlatformException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            resolution_hint="Verify the resource identifier and tenant context.",
            details=details,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationException(PlatformException):
    """Raised when business logic or input validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            resolution_hint="Check submitted fields and ensure all required conditions are met.",
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class PermissionDeniedException(PlatformException):
    """Raised when an actor lacks the required capability or ownership scope."""

    def __init__(self, action: str, resource: str):
        super().__init__(
            code="PERMISSION_DENIED",
            message=f"Access denied for action '{action}' on resource '{resource}'.",
            resolution_hint="Request additional permissions or check company tenant assignment.",
            details={"action": action, "resource": resource},
            status_code=status.HTTP_403_FORBIDDEN,
        )


class KernelBootException(PlatformException):
    """Raised when the micro-kernel encounters a fatal error during boot."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="KERNEL_BOOT_ERROR",
            message=message,
            resolution_hint="Check module manifests, circular dependencies, or environment variables.",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class CircularDependencyError(KernelBootException):
    """Raised when a circular reference is detected in module dependencies."""

    def __init__(self, cycle: list):
        cycle_str = " -> ".join(cycle)
        super().__init__(
            message=f"Circular dependency detected in module DAG: {cycle_str}",
            details={"cycle": cycle},
        )


class MissingDependencyError(KernelBootException):
    """Raised when a required module dependency is not found."""

    def __init__(self, module: str, missing_dep: str):
        super().__init__(
            message=f"Module '{module}' depends on '{missing_dep}', which is not registered or discovered.",
            details={"module": module, "missing_dependency": missing_dep},
        )


class ConcurrencyConflictException(PlatformException):
    """Raised when an optimistic concurrency conflict (lost update) is detected."""

    def __init__(
        self,
        resource: str = "",
        expected_version: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        base_details = {"resource": resource, "expected_version": expected_version}
        if details:
            base_details.update(details)
        super().__init__(
            code="CONCURRENCY_CONFLICT",
            message="The record was modified or deleted by another concurrent transaction.",
            resolution_hint="Reload the latest version of the record, reapply your changes, and retry.",
            details=base_details,
            status_code=status.HTTP_409_CONFLICT,
        )


async def stale_data_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI exception handler converting SQLAlchemy StaleDataError into 409 Conflict envelope."""
    conflict = ConcurrencyConflictException(
        details={"error": "Database row version mismatch; record was modified concurrently."}
    )
    return JSONResponse(status_code=conflict.status_code, content=conflict.to_envelope())


async def platform_exception_handler(request: Request, exc: PlatformException) -> JSONResponse:
    """FastAPI exception handler for PlatformException hierarchy."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI exception handler formatting Pydantic validation errors into standard envelopes."""
    from fastapi.encoders import jsonable_encoder
    details = {"errors": jsonable_encoder(exc.errors())}
    envelope = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The request payload failed schema validation.",
            "resolution_hint": "Inspect 'details.errors' to correct field types, requirements, or values.",
            "details": details,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=envelope)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler for unexpected server errors."""
    envelope = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred processing your request.",
            "resolution_hint": "Inspect server logs with the error timestamp or contact system administrators.",
            "details": {"exception_type": type(exc).__name__, "description": str(exc)},
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=envelope)

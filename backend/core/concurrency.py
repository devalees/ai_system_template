"""Optimistic Concurrency Control (OCC) utilities and version assertions."""

from typing import Any, Optional, Dict
from sqlalchemy.orm.exc import StaleDataError

from core.exceptions import ConcurrencyConflictException, stale_data_exception_handler
from core.base_models import OptimisticLockingMixin


def assert_version_match(
    record: Any,
    expected_version: Optional[int],
    resource_name: Optional[str] = None,
) -> None:
    """Validate that the record's current version matches the expected version from client.
    
    Raises:
        ConcurrencyConflictException: If expected_version is provided and differs from record.version_id.
    """
    if expected_version is None:
        return

    current_version = getattr(record, "version_id", None)
    if current_version is not None and current_version != expected_version:
        name = resource_name or record.__class__.__name__
        raise ConcurrencyConflictException(
            resource=name,
            expected_version=expected_version,
            details={
                "resource": name,
                "current_version": current_version,
                "expected_version": expected_version,
                "message": (
                    f"Conflict on {name}: current database version is {current_version}, "
                    f"but update payload expected version {expected_version}."
                ),
            },
        )


__all__ = [
    "OptimisticLockingMixin",
    "ConcurrencyConflictException",
    "assert_version_match",
    "stale_data_exception_handler",
]

"""
Model Audit Registry for Comprehensive Activity Audit Trail.

Maintains the set of models opted in for automated change diffing and lifecycle logging.
Supports explicit registration, decorator syntax, and introspection flags.
"""

from typing import Any, Set, Type
from django.db import models

_AUDITABLE_MODELS: Set[Type[models.Model]] = set()


def register_auditable(model_class: Type[models.Model]) -> Type[models.Model]:
    """
    Register a model class to be automatically monitored by audit signals.

    Can be used as a function or class decorator:
        @register_auditable
        class Invoice(models.Model):
            ...
    """
    if issubclass(model_class, models.Model):
        _AUDITABLE_MODELS.add(model_class)
        # Also set flag on class for fast lookups
        setattr(model_class, "_audit_enabled", True)
    return model_class


def unregister_auditable(model_class: Type[models.Model]):
    """Unregister a model class from audit signal monitoring."""
    if model_class in _AUDITABLE_MODELS:
        _AUDITABLE_MODELS.remove(model_class)
    if hasattr(model_class, "_audit_enabled"):
        setattr(model_class, "_audit_enabled", False)


def is_model_auditable(model_or_instance: Any) -> bool:
    """
    Check if a model class or model instance is registered or flagged for auditing.
    """
    if model_or_instance is None:
        return False

    model = model_or_instance if isinstance(model_or_instance, type) else model_or_instance.__class__

    # Never audit the audit log itself or internal migration/session tables
    app_label = getattr(getattr(model, "_meta", None), "app_label", "")
    if app_label in ("audit", "contenttypes", "sessions", "admin"):
        return False

    # Check explicit flag on model
    if getattr(model, "audit_enabled", False) or getattr(model, "_audit_enabled", False):
        return True

    # Check dynamic model metadata flag
    if getattr(model, "_is_auditable", False):
        return True

    # Check in-memory registry
    if model in _AUDITABLE_MODELS:
        return True

    return False

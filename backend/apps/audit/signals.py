"""
Automated Model Diffing & Security Event Signal Receivers.

Listens to Django model lifecycle signals (pre_save, post_save, post_delete)
and authentication events (user_logged_in, user_logged_out, user_login_failed)
to emit immutable ActivityLog records with accurate before/after attribute diffs.
"""

import datetime
import decimal
import logging
import uuid
from typing import Any, Dict, Optional

from django.contrib.auth import user_logged_in, user_logged_out, user_login_failed
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.audit.context import (
    get_audit_actor,
    get_audit_ip,
    get_audit_metadata,
    get_audit_request_id,
    get_audit_user_agent,
)
from apps.audit.models import ActivityLog
from apps.audit.registry import is_model_auditable
from apps.core.middleware import get_current_user
from apps.tenants.context import get_current_tenant

logger = logging.getLogger("apps.audit")

EXCLUDED_DIFF_FIELDS = {
    "updated_at",
    "modified_at",
    "_state",
}

SENSITIVE_FIELD_NAMES = {
    "password",
    "secret",
    "secret_key",
    "token",
    "api_key",
    "refresh_token",
    "access_token",
}


def serialize_value(val: Any) -> Any:
    """Safely convert complex Python types into JSON-serializable primitives."""
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, models.Model):
        return {
            "id": str(val.pk),
            "label": str(val)[:100],
        }
    if isinstance(val, (list, tuple, set)):
        return [serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    return val


def extract_field_snapshot(instance: models.Model) -> Dict[str, Any]:
    """Extract a dictionary of field names to serialized values for diffing."""
    snapshot: Dict[str, Any] = {}
    for field in instance._meta.fields:
        field_name = field.name
        if field_name in EXCLUDED_DIFF_FIELDS:
            continue

        if any(sensitive in field_name.lower() for sensitive in SENSITIVE_FIELD_NAMES):
            val = getattr(instance, field_name, None)
            snapshot[field_name] = "[PROTECTED]" if val else None
            continue

        try:
            val = getattr(instance, field_name, None)
            snapshot[field_name] = serialize_value(val)
        except Exception:
            snapshot[field_name] = None

    return snapshot


@receiver(pre_save)
def audit_pre_save_receiver(sender, instance, **kwargs):
    """
    Capture the prior state of the model before changes are written to the database.
    """
    if not is_model_auditable(sender):
        return

    # If it's a new instance without a primary key or state is adding, no old values exist
    if getattr(instance, "_state", None) and instance._state.adding:
        instance._audit_old_snapshot = None
        return

    if not instance.pk:
        instance._audit_old_snapshot = None
        return

    try:
        # Fetch the original instance from the database using all_objects or _base_manager
        # to ensure soft-deleted or filtered records are correctly inspected
        manager = getattr(sender, "all_objects", getattr(sender, "_base_manager", sender._default_manager))
        original = manager.filter(pk=instance.pk).first()
        if original:
            instance._audit_old_snapshot = extract_field_snapshot(original)
        else:
            instance._audit_old_snapshot = None
    except Exception as exc:
        logger.debug("Failed to extract pre-save audit snapshot for %s: %s", sender, exc)
        instance._audit_old_snapshot = None


@receiver(post_save)
def audit_post_save_receiver(sender, instance, created: bool, **kwargs):
    """
    Compare previous snapshot with current state and generate an ActivityLog entry.
    """
    if not is_model_auditable(sender):
        return

    try:
        new_snapshot = extract_field_snapshot(instance)
        diff: Dict[str, Dict[str, Any]] = {}
        action = ActivityLog.ACTION_CREATE

        if created:
            action = ActivityLog.ACTION_CREATE
            diff = {
                k: {"old": None, "new": v}
                for k, v in new_snapshot.items()
                if v is not None
            }
        else:
            old_snapshot = getattr(instance, "_audit_old_snapshot", None)
            if old_snapshot is None:
                return

            for field, new_val in new_snapshot.items():
                old_val = old_snapshot.get(field)
                if old_val != new_val:
                    diff[field] = {"old": old_val, "new": new_val}

            if not diff:
                # No actual attribute differences; do not generate noisy empty logs
                return

            # Detect soft-delete or restore if model uses SoftDeleteModel semantics
            if "is_deleted" in diff:
                if diff["is_deleted"]["old"] is False and diff["is_deleted"]["new"] is True:
                    action = ActivityLog.ACTION_DELETE
                elif diff["is_deleted"]["old"] is True and diff["is_deleted"]["new"] is False:
                    action = ActivityLog.ACTION_RESTORE
                else:
                    action = ActivityLog.ACTION_UPDATE
            else:
                action = ActivityLog.ACTION_UPDATE

        # Resolve actor
        actor = get_audit_actor() or get_current_user()
        if actor and not getattr(actor, "is_authenticated", False):
            actor = None

        actor_type = ActivityLog.ACTOR_USER if actor else ActivityLog.ACTOR_SYSTEM

        # Resolve organization
        org = getattr(instance, "organization", None) or get_current_tenant()

        # Resolve ContentType
        ct = ContentType.objects.get_for_model(instance)

        # Create ActivityLog entry
        ActivityLog.objects.create(
            organization=org,
            actor=actor,
            actor_type=actor_type,
            action=action,
            status=ActivityLog.STATUS_SUCCESS,
            content_type=ct,
            object_id=str(instance.pk),
            object_repr=str(instance)[:255],
            changes=diff,
            ip_address=get_audit_ip(),
            user_agent=get_audit_user_agent(),
            request_id=get_audit_request_id(),
            metadata=get_audit_metadata(),
        )
    except Exception as exc:
        logger.exception("Failed to write post_save audit log for %s (%s): %s", sender, instance.pk, exc)


@receiver(post_delete)
def audit_post_delete_receiver(sender, instance, **kwargs):
    """
    Record hard deletion of an auditable model instance.
    """
    if not is_model_auditable(sender):
        return

    try:
        actor = get_audit_actor() or get_current_user()
        if actor and not getattr(actor, "is_authenticated", False):
            actor = None

        actor_type = ActivityLog.ACTOR_USER if actor else ActivityLog.ACTOR_SYSTEM
        org = getattr(instance, "organization", None) or get_current_tenant()
        ct = ContentType.objects.get_for_model(instance)
        snapshot = extract_field_snapshot(instance)

        diff = {
            k: {"old": v, "new": None}
            for k, v in snapshot.items()
            if v is not None
        }

        ActivityLog.objects.create(
            organization=org,
            actor=actor,
            actor_type=actor_type,
            action=ActivityLog.ACTION_HARD_DELETE,
            status=ActivityLog.STATUS_SUCCESS,
            content_type=ct,
            object_id=str(instance.pk),
            object_repr=str(instance)[:255],
            changes=diff,
            ip_address=get_audit_ip(),
            user_agent=get_audit_user_agent(),
            request_id=get_audit_request_id(),
            metadata=get_audit_metadata(),
        )
    except Exception as exc:
        logger.exception("Failed to write post_delete audit log for %s (%s): %s", sender, instance.pk, exc)


# -------------------------------------------------------------------------
# Authentication Security Event Receivers
# -------------------------------------------------------------------------

@receiver(user_logged_in)
def audit_user_logged_in_receiver(sender, request, user, **kwargs):
    """Log successful user authentication event."""
    try:
        ip = get_audit_ip()
        ua = get_audit_user_agent()
        req_id = get_audit_request_id()
        if request:
            if not ip:
                ip = request.META.get("REMOTE_ADDR")
            if not ua:
                ua = request.META.get("HTTP_USER_AGENT", "")

        ct = ContentType.objects.get_for_model(user)
        ActivityLog.objects.create(
            actor=user,
            actor_type=ActivityLog.ACTOR_USER,
            action=ActivityLog.ACTION_LOGIN,
            status=ActivityLog.STATUS_SUCCESS,
            content_type=ct,
            object_id=str(user.pk),
            object_repr=user.username,
            ip_address=ip,
            user_agent=ua,
            request_id=req_id,
            metadata={"auth_backend": str(user.backend) if hasattr(user, "backend") else ""},
        )
    except Exception as exc:
        logger.exception("Failed to record login audit log for %s: %s", user, exc)


@receiver(user_logged_out)
def audit_user_logged_out_receiver(sender, request, user, **kwargs):
    """Log user logout event."""
    try:
        if not user or not user.is_authenticated:
            return

        ip = get_audit_ip()
        ua = get_audit_user_agent()
        req_id = get_audit_request_id()
        if request:
            if not ip:
                ip = request.META.get("REMOTE_ADDR")
            if not ua:
                ua = request.META.get("HTTP_USER_AGENT", "")

        ct = ContentType.objects.get_for_model(user)
        ActivityLog.objects.create(
            actor=user,
            actor_type=ActivityLog.ACTOR_USER,
            action=ActivityLog.ACTION_LOGOUT,
            status=ActivityLog.STATUS_SUCCESS,
            content_type=ct,
            object_id=str(user.pk),
            object_repr=user.username,
            ip_address=ip,
            user_agent=ua,
            request_id=req_id,
        )
    except Exception as exc:
        logger.exception("Failed to record logout audit log for %s: %s", user, exc)


@receiver(user_login_failed)
def audit_user_login_failed_receiver(sender, credentials, request, **kwargs):
    """Log failed authentication attempt for security monitoring."""
    try:
        attempted_username = (
            credentials.get("username")
            or credentials.get("email")
            or "unknown"
        )
        ip = get_audit_ip()
        ua = get_audit_user_agent()
        req_id = get_audit_request_id()
        if request:
            if not ip:
                ip = request.META.get("REMOTE_ADDR")
            if not ua:
                ua = request.META.get("HTTP_USER_AGENT", "")

        ActivityLog.objects.create(
            actor=None,
            actor_type=ActivityLog.ACTOR_ANONYMOUS,
            action=ActivityLog.ACTION_LOGIN_FAILED,
            status=ActivityLog.STATUS_FAILURE,
            object_repr=f"Attempted: {attempted_username}",
            ip_address=ip,
            user_agent=ua,
            request_id=req_id,
            metadata={"attempted_username": attempted_username},
        )
    except Exception as exc:
        logger.exception("Failed to record login_failed audit log: %s", exc)

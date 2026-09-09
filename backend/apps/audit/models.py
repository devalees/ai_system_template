"""
Data models for Comprehensive Activity Audit Trail.

Provides:
- ActivityLog: Immutable, append-only audit trail capturing user, bot, and system
  events, attribute change diffs, security authentications, and multi-tenant scoping.
"""

from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDModel


class ImmutabilityError(PermissionDenied):
    """Raised when attempting to modify or illegally delete an immutable audit log entry."""
    pass


class ActivityLogQuerySet(models.QuerySet):
    """QuerySet enforcing immutability on bulk operations."""

    def delete(self, allow_purge: bool = False):
        """Disallow bulk deletion unless allow_purge=True is provided."""
        if not allow_purge:
            raise ImmutabilityError(_("ActivityLog entries are immutable and cannot be bulk deleted."))
        return super().delete()

    def update(self, **kwargs):
        """Disallow bulk updates on immutable audit log entries."""
        raise ImmutabilityError(_("ActivityLog entries are immutable and cannot be updated."))


class ActivityLog(UUIDModel):
    """
    Immutable, append-only log entry recording a human, bot, or system action.
    """
    objects = ActivityLogQuerySet.as_manager()

    # Actor Types
    ACTOR_USER = "user"
    ACTOR_BOT = "bot"
    ACTOR_SYSTEM = "system"
    ACTOR_ANONYMOUS = "anonymous"

    ACTOR_TYPE_CHOICES = [
        (ACTOR_USER, _("Human User")),
        (ACTOR_BOT, _("Bot Service Account")),
        (ACTOR_SYSTEM, _("System / Background Process")),
        (ACTOR_ANONYMOUS, _("Anonymous / Unauthenticated")),
    ]

    # Action Classifications
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_RESTORE = "restore"
    ACTION_HARD_DELETE = "hard_delete"
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_LOGIN_FAILED = "login_failed"
    ACTION_EXPORT = "export"
    ACTION_CUSTOM = "custom"

    ACTION_CHOICES = [
        (ACTION_CREATE, _("Create")),
        (ACTION_UPDATE, _("Update")),
        (ACTION_DELETE, _("Delete (Soft)")),
        (ACTION_RESTORE, _("Restore")),
        (ACTION_HARD_DELETE, _("Hard Delete")),
        (ACTION_LOGIN, _("Login")),
        (ACTION_LOGOUT, _("Logout")),
        (ACTION_LOGIN_FAILED, _("Login Failed")),
        (ACTION_EXPORT, _("Export")),
        (ACTION_CUSTOM, _("Custom Action")),
    ]

    # Execution Status
    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"
    STATUS_WARNING = "warning"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, _("Success")),
        (STATUS_FAILURE, _("Failure")),
        (STATUS_WARNING, _("Warning")),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        db_index=True,
        verbose_name=_("Organization"),
        help_text=_("Associated workspace / tenant (null for system-level actions).")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        db_index=True,
        verbose_name=_("Actor"),
        help_text=_("The user or service account performing the action.")
    )
    actor_type = models.CharField(
        max_length=32,
        choices=ACTOR_TYPE_CHOICES,
        default=ACTOR_USER,
        db_index=True,
        verbose_name=_("Actor Type"),
    )
    action = models.CharField(
        max_length=64,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name=_("Action"),
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_SUCCESS,
        db_index=True,
        verbose_name=_("Status"),
    )

    # Generic Foreign Key to any audited model (integer or UUID primary key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Content Type"),
    )
    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Object ID"),
    )
    content_object = GenericForeignKey("content_type", "object_id")

    object_repr = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Target Representation"),
        help_text=_("Human-readable title or label of target object at time of event.")
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Attribute Changes"),
        help_text=_("Structured diff: {'field_name': {'old': v1, 'new': v2}}.")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("Client IP Address"),
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_("User Agent"),
    )
    request_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name=_("Request Correlation ID"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Context Metadata"),
        help_text=_("Extra telemetry or contextual parameters.")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Timestamp"),
    )

    class Meta:
        verbose_name = _("Activity Log")
        verbose_name_plural = _("Activity Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action", "-timestamp"], name="idx_audit_action_ts"),
            models.Index(fields=["organization", "-timestamp"], name="idx_audit_org_ts"),
            models.Index(fields=["actor", "-timestamp"], name="idx_audit_actor_ts"),
            models.Index(fields=["content_type", "object_id"], name="idx_audit_target"),
        ]

    def __str__(self) -> str:
        actor_name = self.actor.username if self.actor else self.get_actor_type_display()
        target = f" on {self.object_repr}" if self.object_repr else ""
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {actor_name} -> {self.get_action_display()}{target} ({self.status})"

    def save(self, *args, **kwargs):
        """Enforce strict immutability: records cannot be updated once created."""
        if not self._state.adding and self.pk:
            if ActivityLog.objects.filter(pk=self.pk).exists():
                raise ImmutabilityError(_("ActivityLog entries are immutable and cannot be updated."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enforce strict immutability: records cannot be deleted without explicit bypass."""
        allow_purge = kwargs.pop("allow_purge", False)
        if not allow_purge:
            raise ImmutabilityError(_("ActivityLog entries are immutable and cannot be deleted."))
        super().delete(*args, **kwargs)

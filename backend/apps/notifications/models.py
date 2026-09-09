"""
Data models for Universal Notifications Engine.

Provides:
- Notification: Multi-tenant, soft-deletable notification record targeting a user recipient.
- NotificationPreference: Per-user multi-channel notification toggles and endpoints.
"""

from typing import Any, Dict, Optional

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDModel, TimeStampedModel, SoftDeleteModel
from apps.tenants.base_models import TenantAwareModel


class Notification(TenantAwareModel, SoftDeleteModel):
    """
    Notification entry sent to a specific user recipient within an organization workspace.
    """
    # Level choices
    LEVEL_INFO = "info"
    LEVEL_SUCCESS = "success"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"

    LEVEL_CHOICES = [
        (LEVEL_INFO, _("Information")),
        (LEVEL_SUCCESS, _("Success")),
        (LEVEL_WARNING, _("Warning")),
        (LEVEL_ERROR, _("Error")),
    ]

    # Delivery Channel choices
    CHANNEL_IN_APP = "in_app"
    CHANNEL_EMAIL = "email"
    CHANNEL_WEBHOOK = "webhook"
    CHANNEL_SLACK = "slack"
    CHANNEL_HERMES = "hermes"

    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, _("In-App Notification")),
        (CHANNEL_EMAIL, _("Email")),
        (CHANNEL_WEBHOOK, _("HTTP Webhook")),
        (CHANNEL_SLACK, _("Slack Alert")),
        (CHANNEL_HERMES, _("Hermes AI Agent")),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
        verbose_name=_("Recipient"),
        help_text=_("Target user receiving this notification.")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
        verbose_name=_("Actor / Sender"),
        help_text=_("User or bot profile that triggered this notification (null if system).")
    )
    level = models.CharField(
        max_length=16,
        choices=LEVEL_CHOICES,
        default=LEVEL_INFO,
        db_index=True,
        verbose_name=_("Notification Level"),
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
        help_text=_("Brief notification title or summary.")
    )
    message = models.TextField(
        verbose_name=_("Message Content"),
        help_text=_("Full text body of the notification.")
    )
    action_url = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("Action URL"),
        help_text=_("Optional relative or absolute link for interactive navigation.")
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Read At"),
        help_text=_("Timestamp when recipient marked this notification as read.")
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Read"),
        help_text=_("Indicates if the notification has been read.")
    )
    channel = models.CharField(
        max_length=32,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_IN_APP,
        db_index=True,
        verbose_name=_("Delivery Channel"),
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Extra Data"),
        help_text=_("Structured JSON payload context (e.g. task_id, audit_id).")
    )

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["organization", "recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"[{self.level.upper()}] {self.title} -> {self.recipient.username}"

    def mark_as_read(self) -> None:
        """Mark notification as read and record timestamp if not already read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])


class NotificationPreference(UUIDModel, TimeStampedModel):
    """
    User notification delivery preferences and webhook configuration endpoints.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name=_("User"),
    )
    in_app_enabled = models.BooleanField(
        default=True,
        verbose_name=_("In-App Enabled"),
        help_text=_("Receive notifications in system dashboard.")
    )
    email_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Email Enabled"),
        help_text=_("Receive email notifications for important alerts.")
    )
    webhook_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Webhook Enabled"),
        help_text=_("Dispatch HTTP POST payload to external webhook URL.")
    )
    slack_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Slack Alerts Enabled"),
        help_text=_("Dispatch alerts to Slack incoming webhook URL.")
    )
    webhook_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("Webhook Endpoint URL"),
    )
    slack_webhook_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("Slack Incoming Webhook URL"),
    )
    channel_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Channel Configurations"),
        help_text=_("Custom channel metadata (e.g. min level thresholds).")
    )

    class Meta:
        verbose_name = _("Notification Preference")
        verbose_name_plural = _("Notification Preferences")

    def __str__(self) -> str:
        return f"Notification Preferences for {self.user.username}"

"""
Data models for Developer API Gateway, Scoped Keys & Inbound Webhooks.

Provides:
- APIKey: Cryptographically hashed developer API keys with scopes, IP allowlists, and expiration dates.
- InboundWebhook: Endpoint configurations for third-party SaaS webhook ingestion.
- WebhookEvent: Immutable archival and status tracker for received webhook events.
"""

import hashlib
import secrets
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel
from apps.tenants.base_models import TenantAwareModel


class APIKey(TenantAwareModel, SoftDeleteModel):
    """
    Developer API key with hashed secret, granular permission scopes, and IP allowlists.
    Raw keys (e.g. 'agy_live_...') are generated once and never stored in plain text.
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_("Key Name"),
        help_text=_("Human-readable label identifying this API key (e.g. 'Stripe Integration Key').")
    )
    prefix = models.CharField(
        max_length=16,
        db_index=True,
        verbose_name=_("Key Prefix"),
        help_text=_("Public key prefix for fast database lookup (e.g. 'agy_live_a1b2').")
    )
    hashed_key = models.CharField(
        max_length=128,
        verbose_name=_("Hashed Secret Key"),
        help_text=_("SHA-256 hash digest of the full secret key.")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name=_("User Account"),
        help_text=_("User or bot account bound to this API key.")
    )
    scopes = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Permission Scopes"),
        help_text=_("List of allowed action scopes (e.g. ['read', 'write', 'tasks:create']).")
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Allowed IP Addresses"),
        help_text=_("Optional list of allowed client IP addresses/CIDR blocks.")
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expires At"),
        help_text=_("Expiration timestamp. Null indicates an unexpiring key.")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates if key is operational and authorized.")
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Used At"),
        help_text=_("Timestamp of most recent successful authentication.")
    )

    class Meta:
        verbose_name = _("Developer API Key")
        verbose_name_plural = _("Developer API Keys")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["prefix", "is_active"]),
            models.Index(fields=["organization", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}...)"

    @classmethod
    def generate_key(
        cls,
        name: str,
        user,
        organization=None,
        scopes: Optional[List[str]] = None,
        expires_at=None,
        allowed_ips: Optional[List[str]] = None,
        prefix_tag: str = "agy_live",
    ) -> Tuple["APIKey", str]:
        """
        Generate a new cryptographically secure APIKey.
        Returns a tuple of (APIKey_instance, raw_secret_key_string).
        """
        raw_token = secrets.token_hex(24)
        raw_secret_key = f"{prefix_tag}_{raw_token}"
        prefix = raw_secret_key[:12]
        hashed = hashlib.sha256(raw_secret_key.encode("utf-8")).hexdigest()

        key_instance = cls.objects.create(
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            user=user,
            organization=organization,
            scopes=scopes or ["read", "write"],
            expires_at=expires_at,
            allowed_ips=allowed_ips or [],
            is_active=True,
        )
        return key_instance, raw_secret_key

    def verify_key(self, raw_key: str) -> bool:
        """Verify if a raw key string matches this stored hashed key."""
        hashed_input = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return secrets.compare_digest(self.hashed_key, hashed_input)

    @property
    def is_expired(self) -> bool:
        """Check if key has passed its expiration timestamp."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    def record_usage(self) -> None:
        """Record usage timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at", "updated_at"])


class InboundWebhook(TenantAwareModel, SoftDeleteModel):
    """
    Endpoint configuration for third-party SaaS inbound webhook ingestion.
    """
    PROVIDER_GITHUB = "github"
    PROVIDER_STRIPE = "stripe"
    PROVIDER_SLACK = "slack"
    PROVIDER_CUSTOM = "custom"

    PROVIDER_CHOICES = [
        (PROVIDER_GITHUB, _("GitHub")),
        (PROVIDER_STRIPE, _("Stripe")),
        (PROVIDER_SLACK, _("Slack")),
        (PROVIDER_CUSTOM, _("Custom HMAC")),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name=_("Webhook Name"),
        help_text=_("Display label (e.g. 'GitHub Repository Push Webhook').")
    )
    endpoint_slug = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name=_("Endpoint Slug"),
        help_text=_("Unique URL path parameter (e.g. '/api/v1/gateway/webhooks/github-push/ingest/').")
    )
    secret_token = models.CharField(
        max_length=255,
        verbose_name=_("Secret Token / HMAC Key"),
        help_text=_("Shared secret used to compute and verify incoming HMAC signatures.")
    )
    provider = models.CharField(
        max_length=64,
        choices=PROVIDER_CHOICES,
        default=PROVIDER_CUSTOM,
        verbose_name=_("Provider"),
        help_text=_("Provider signature format for HMAC verification.")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Enables or disables inbound event ingestion.")
    )

    class Meta:
        verbose_name = _("Inbound Webhook Endpoint")
        verbose_name_plural = _("Inbound Webhook Endpoints")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} [{self.provider}] ({self.endpoint_slug})"


class WebhookEvent(TenantAwareModel, SoftDeleteModel):
    """
    Immutable log record archiving received webhook events and execution state.
    """
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_PROCESSED, _("Processed")),
        (STATUS_FAILED, _("Failed")),
    ]

    webhook = models.ForeignKey(
        InboundWebhook,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Inbound Webhook"),
    )
    event_type = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name=_("Event Type"),
        help_text=_("Detected provider event name (e.g. 'push', 'payment_intent.succeeded').")
    )
    payload = models.JSONField(
        default=dict,
        verbose_name=_("Payload Body"),
        help_text=_("Raw JSON payload received from sender.")
    )
    headers = models.JSONField(
        default=dict,
        verbose_name=_("HTTP Headers"),
        help_text=_("Received HTTP headers dictionary.")
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name=_("Execution Status"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
        help_text=_("Details if processing or signature validation failed.")
    )

    class Meta:
        verbose_name = _("Webhook Event Log")
        verbose_name_plural = _("Webhook Event Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "status", "-created_at"]),
            models.Index(fields=["organization", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"Event '{self.event_type}' via {self.webhook.name} [{self.status}]"

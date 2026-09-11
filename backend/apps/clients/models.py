"""
Data models for Client Management.

Provides:
- Client: External business, company, or institutional client entity belonging to an Organization tenant.
  Includes 1-to-many user relationship, AI service gatekeeping (is_ai_enabled), and dollar budget milestones.
"""

import os
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDModel, SoftDeleteModel, AuditableModel
from apps.tenants.models import Organization


class Client(UUIDModel, SoftDeleteModel, AuditableModel):
    """
    Represents an external business client, company, or institutional customer
    operating within an Organization tenant.
    """
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Active")),
        (STATUS_INACTIVE, _("Inactive")),
        (STATUS_SUSPENDED, _("Suspended")),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="clients",
        verbose_name=_("Organization / Tenant"),
        help_text=_("Host tenant firm/organization that owns this client account.")
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("Client Name"),
        help_text=_("Display name of the client company or account (e.g. Acme Corporation).")
    )
    slug = models.SlugField(
        max_length=100,
        db_index=True,
        verbose_name=_("Client Slug"),
        help_text=_("Unique identifier slug within the organization (e.g. acme-corp).")
    )
    primary_contact_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name=_("Primary Contact Name"),
        help_text=_("Main point of contact at the client organization.")
    )
    primary_contact_email = models.EmailField(
        blank=True,
        default="",
        verbose_name=_("Primary Contact Email"),
        help_text=_("Main contact email for correspondence and notifications.")
    )
    primary_contact_phone = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Primary Contact Phone"),
        help_text=_("Direct telephone or mobile contact.")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
        verbose_name=_("Account Status"),
        help_text=_("Operational state of the client account.")
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Administrative Notes"),
        help_text=_("Internal context, SLA specifics, or account preferences.")
    )

    # AI Service & Dollar Budget Governance
    is_ai_enabled = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("AI Service Enabled"),
        help_text=_("Master entitlement gate. If disabled, client cannot use AI concierge services.")
    )
    ai_budget_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("15.00"),
        verbose_name=_("AI Budget (USD)"),
        help_text=_("Dollar expenditure ceiling allocated for this client.")
    )
    ai_spend_usd = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("0.0000"),
        verbose_name=_("Cumulative AI Spend (USD)"),
        help_text=_("Real-time dollar cost consumed across AI concierge interactions.")
    )

    class Meta:
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")
        ordering = ["name"]
        unique_together = [("organization", "slug")]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.name})"

    @property
    def ai_budget_percentage(self) -> float:
        """Calculate the percentage of allocated budget consumed."""
        if not self.ai_budget_usd or self.ai_budget_usd <= 0:
            return 0.0
        pct = (float(self.ai_spend_usd) / float(self.ai_budget_usd)) * 100.0
        return round(pct, 2)

    @property
    def ai_budget_status(self) -> str:
        """
        Evaluate expenditure against the 4 percentage milestones:
        - healthy: spend < 50%
        - velocity_check: 50% <= spend < 75%
        - warning: 75% <= spend < 100%
        - exceeded: spend >= 100%
        """
        if not self.is_ai_enabled:
            return "disabled"
        pct = self.ai_budget_percentage
        if pct >= 100.0:
            return "exceeded"
        elif pct >= 75.0:
            return "warning"
        elif pct >= 50.0:
            return "velocity_check"
        return "healthy"

    def can_use_ai(self) -> bool:
        """Check whether the client is authorized to initiate AI tasks."""
        if not self.is_ai_enabled or self.status != self.STATUS_ACTIVE:
            return False
        return self.ai_spend_usd < self.ai_budget_usd

    @property
    def linked_users_count(self) -> int:
        """Return the count of user accounts linked to this client."""
        return self.users.count() if hasattr(self, "users") else 0

    def ensure_storage_dir(self) -> str:
        """
        Ensure dedicated client physical storage directory exists under MEDIA_ROOT/documents/clients/<client_id>/.
        Returns the absolute path to the directory.
        """
        media_root = getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media")
        client_dir = os.path.join(str(media_root), "documents", "clients", str(self.id))
        os.makedirs(client_dir, exist_ok=True)
        return client_dir

    @property
    def storage_dir(self) -> str:
        """Return the physical storage directory path for this client."""
        return self.ensure_storage_dir()

    def save(self, *args, **kwargs):
        """Persist client record and auto-provision dedicated media directory."""
        super().save(*args, **kwargs)
        try:
            self.ensure_storage_dir()
        except Exception:
            pass


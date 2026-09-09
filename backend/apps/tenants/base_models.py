"""
Abstract Base Models for Multi-Tenant Data Isolation.

Provides:
- TenantAwareModel: Abstract model with auto-scoped organization foreign key,
  context-aware saving, and TenantManager integration.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AuditableModel
from apps.tenants.context import get_current_tenant
from apps.tenants.managers import TenantManager, TenantAllManager


class TenantAwareModel(AuditableModel):
    """
    Abstract base model providing automatic row-level tenant isolation.

    Features:
    - Guaranteed indexed foreign key to `Organization`.
    - Auto-populates `self.organization` from `get_current_tenant()` on save.
    - Default `objects` manager auto-scopes all queries to active tenant.
    - Explicit `all_objects` manager for unfiltered system access.
    """
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
        verbose_name=_("Organization"),
        help_text=_("The organization / workspace owning this record.")
    )

    objects = TenantManager()
    all_objects = TenantAllManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Automatically bind record to active tenant if organization is omitted.
        """
        if not hasattr(self, "organization") or self.organization_id is None:
            active_tenant = get_current_tenant()
            if active_tenant is None:
                try:
                    from apps.tenants.models import Organization
                    active_tenant = (
                        Organization.objects.filter(slug="default", is_active=True).first()
                        or Organization.objects.filter(is_active=True).first()
                    )
                except Exception:
                    pass
            if active_tenant is not None:
                self.organization = active_tenant
        super().save(*args, **kwargs)

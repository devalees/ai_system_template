"""
Multi-Tenant QuerySets and Managers.

Provides automatic row-level tenant isolation, integration with SoftDeleteModel,
and explicit bypass managers for cross-tenant operations.
"""

from django.db import models
from apps.core.models import SoftDeleteQuerySet
from apps.tenants.context import get_current_tenant, is_tenant_isolation_bypassed


class TenantQuerySet(SoftDeleteQuerySet):
    """QuerySet that supports explicit or implicit tenant scoping with soft-delete support."""

    def filter_by_tenant(self, tenant=None):
        """Explicitly scope this queryset to a specific organization or current tenant."""
        target = tenant or get_current_tenant()
        if target:
            return self.filter(organization=target)
        return self


class TenantManager(models.Manager):
    """
    Default manager for TenantAwareModel.

    Automatically filters records by:
    1. is_deleted=False (if the model inherits SoftDeleteModel)
    2. organization=get_current_tenant() (if an active tenant is present in context)
    """

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)

        # Exclude soft-deleted records if model supports soft deletion
        if hasattr(self.model, "is_deleted"):
            qs = qs.alive()

        # Apply tenant isolation unless explicitly bypassed
        if not is_tenant_isolation_bypassed():
            tenant = get_current_tenant()
            if tenant is not None:
                qs = qs.filter(organization=tenant)

        return qs

    def dead(self):
        """Return soft-deleted records, optionally scoped to tenant."""
        qs = TenantQuerySet(self.model, using=self._db).dead()
        if not is_tenant_isolation_bypassed():
            tenant = get_current_tenant()
            if tenant is not None:
                qs = qs.filter(organization=tenant)
        return qs

    def alive(self):
        return self.get_queryset()

    def restore(self):
        return self.get_queryset().restore()

    def hard_delete(self):
        return self.get_queryset().hard_delete()


class TenantAllManager(models.Manager):
    """
    Unfiltered manager for TenantAwareModel.

    Bypasses both tenant filtering and soft-delete filtering for system migrations,
    superuser cross-tenant analytics, and internal audits.
    """

    def get_queryset(self):
        return models.QuerySet(self.model, using=self._db)

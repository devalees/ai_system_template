"""
Core Foundation Abstract Models.

Provides standardized, reusable abstract base models:
- `TimeStampedModel`: Automatic created_at / updated_at timestamps.
- `UUIDModel`: Non-enumerable UUIDv4 primary keys.
- `SoftDeleteModel`: Paranoid model with safe soft deletion, restore, and dual managers.
- `AuditableModel`: Context-aware created_by / updated_by tracking via middleware.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.middleware import get_current_authenticated_user


class TimeStampedModel(models.Model):
    """
    Abstract model providing automatic timestamp tracking.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
        help_text=_("Timestamp when this record was originally created.")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name=_("Updated At"),
        help_text=_("Timestamp when this record was last modified.")
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class UUIDModel(models.Model):
    """
    Abstract model providing a distributed UUIDv4 primary key to prevent ID enumeration.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
        help_text=_("Unique universal identifier for this record.")
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """
    Custom QuerySet supporting bulk soft-delete, hard-delete, and restoration.
    """

    def delete(self, soft: bool = True):
        """Perform soft delete by default, or hard delete if soft=False."""
        if soft:
            return self.update(is_deleted=True, deleted_at=timezone.now())
        return super().delete()

    def hard_delete(self):
        """Permanently remove records from the database."""
        return super().delete()

    def restore(self):
        """Restore previously soft-deleted records."""
        return self.update(is_deleted=False, deleted_at=None)

    def alive(self):
        """Return only active, non-deleted records."""
        return self.filter(is_deleted=False)

    def dead(self):
        """Return only soft-deleted records."""
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """
    Default manager filtering out soft-deleted records.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def hard_delete(self):
        return self.get_queryset().hard_delete()

    def restore(self):
        return self.get_queryset().restore()

    def dead(self):
        return SoftDeleteQuerySet(self.model, using=self._db).dead()


class SoftDeleteAllManager(models.Manager):
    """
    Manager returning all records, including soft-deleted ones.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Abstract model implementing paranoid/soft-deletion semantics.

    Records marked as deleted are hidden from standard QuerySets while
    remaining recoverable via `.restore()` or `all_objects`.
    """
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Deleted"),
        help_text=_("Indicates if this record is soft-deleted.")
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deleted At"),
        help_text=_("Timestamp when this record was soft-deleted.")
    )

    # Standard manager excludes soft-deleted records
    objects = SoftDeleteManager()
    # Unfiltered manager includes all records
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, soft: bool = True):
        """Soft-delete by default, or permanently delete if soft=False."""
        if soft:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(update_fields=["is_deleted", "deleted_at"], using=using)
            return 1, {self._meta.label: 1}
        return super().delete(using=using, keep_parents=keep_parents)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently remove this record from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self, using=None):
        """Restore this soft-deleted record back to active state."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"], using=using)


class AuditableModel(models.Model):
    """
    Abstract model capturing created_by and updated_by actors automatically
    using the active request context from CurrentUserMiddleware.
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name=_("Created By"),
        help_text=_("User or service account who created this record.")
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name=_("Updated By"),
        help_text=_("User or service account who last updated this record.")
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Automatically populate actor fields from active request context."""
        user = get_current_authenticated_user()
        if user:
            if (self._state.adding or not self.created_by_id) and not self.created_by_id:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)


class AppSettingValue(TimeStampedModel):
    """
    Relational storage for application-level settings overriding defaults.
    """
    app_label = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("App Label"),
        help_text=_("Application identifier (e.g. 'automation', 'integration', 'general').")
    )
    key = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("Setting Key"),
        help_text=_("Unique parameter key within the application group.")
    )
    raw_value = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Raw Stored Value"),
        help_text=_("Serialized or encrypted value stored in the database.")
    )
    data_type = models.CharField(
        max_length=20,
        default="str",
        verbose_name=_("Data Type"),
        help_text=_("Data type matching the registered Setting definition.")
    )

    class Meta:
        verbose_name = _("Application Setting Value")
        verbose_name_plural = _("Application Setting Values")
        unique_together = [("app_label", "key")]
        indexes = [
            models.Index(fields=["app_label", "key"]),
        ]

    def __str__(self):
        return f"{self.app_label}.{self.key}"

    @classmethod
    def get_cache_key(cls, app_label: str, key: str) -> str:
        """Generate standardized Redis cache key."""
        return f"core:setting:{app_label}:{key}"


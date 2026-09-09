"""
Signals for apps.core.

Handles automatic Redis cache invalidation whenever an AppSettingValue is saved or deleted.
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.core.models import AppSettingValue


@receiver(post_save, sender=AppSettingValue)
def invalidate_setting_cache_on_save(sender, instance, **kwargs):
    """Invalidate Redis cache key when an AppSettingValue is updated or created."""
    cache_key = instance.get_cache_key(instance.app_label, instance.key)
    cache.delete(cache_key)


@receiver(post_delete, sender=AppSettingValue)
def invalidate_setting_cache_on_delete(sender, instance, **kwargs):
    """Invalidate Redis cache key when an AppSettingValue is deleted."""
    cache_key = instance.get_cache_key(instance.app_label, instance.key)
    cache.delete(cache_key)

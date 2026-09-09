"""
Signal receivers for Universal Notifications Engine.

Handles:
- Auto-provisioning NotificationPreference on User creation.
- Invalidating Redis unread count cache keys on Notification post-save and post-delete.
"""

import logging
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from apps.notifications.models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def get_unread_cache_key(user_id: str, org_id: str = "global") -> str:
    """Construct Redis cache key for unread notification count."""
    return f"notifications:unread_count:{user_id}:{org_id}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_provision_notification_preferences(sender, instance, created: bool, **kwargs):
    """Ensure every User has a NotificationPreference record."""
    if created:
        try:
            NotificationPreference.objects.get_or_create(user=instance)
        except Exception as e:
            logger.error("Failed to auto-provision NotificationPreference for user %s: %s", instance, e)


@receiver(post_save, sender=Notification)
@receiver(post_delete, sender=Notification)
def invalidate_unread_notification_cache(sender, instance: Notification, **kwargs):
    """Invalidate Redis unread count cache for the notification's recipient and workspace."""
    try:
        recipient_id = str(instance.recipient_id)
        org_id = str(instance.organization_id) if instance.organization_id else "global"
        cache_key = get_unread_cache_key(recipient_id, org_id)
        cache.delete(cache_key)
        # Also clear global recipient key if org key was deleted
        cache.delete(get_unread_cache_key(recipient_id, "global"))
    except Exception as e:
        logger.warning("Error invalidating notification unread cache: %s", e)

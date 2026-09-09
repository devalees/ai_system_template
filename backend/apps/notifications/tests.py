"""
Unit tests for Universal Notifications Engine data models, preferences, and signals.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.signals import get_unread_cache_key
from apps.tenants.models import Organization

User = get_user_model()


class NotificationModelTests(TestCase):
    """Test suite verifying Notification and NotificationPreference models."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.sender = User.objects.create_user(username="senderuser", password="password123")

    def test_notification_preference_auto_provisioned(self):
        """Verify NotificationPreference is automatically created when a User is created."""
        pref = NotificationPreference.objects.filter(user=self.user).first()
        self.assertIsNotNone(pref)
        self.assertTrue(pref.in_app_enabled)
        self.assertTrue(pref.email_enabled)
        self.assertFalse(pref.webhook_enabled)
        self.assertFalse(pref.slack_enabled)

    def test_notification_creation_and_defaults(self):
        """Verify Notification record creation with default levels and channels."""
        notification = Notification.objects.create(
            organization=self.org,
            recipient=self.user,
            actor=self.sender,
            level=Notification.LEVEL_SUCCESS,
            title="Task Completed",
            message="Your agent task has finished.",
            action_url="/api/v1/tasks/123/",
            extra_data={"task_id": "123"}
        )
        self.assertEqual(notification.level, Notification.LEVEL_SUCCESS)
        self.assertEqual(notification.channel, Notification.CHANNEL_IN_APP)
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        self.assertIn("TASK COMPLETED", str(notification).upper())

    def test_notification_mark_as_read(self):
        """Verify mark_as_read updates is_read flag and read_at timestamp."""
        notification = Notification.objects.create(
            organization=self.org,
            recipient=self.user,
            title="Alert",
            message="Warning alert"
        )
        self.assertFalse(notification.is_read)
        notification.mark_as_read()
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_redis_cache_invalidation_on_signal(self):
        """Verify post_save signal invalidates Redis unread count cache."""
        cache_key = get_unread_cache_key(str(self.user.id), str(self.org.id))
        cache.set(cache_key, 10, timeout=300)
        self.assertEqual(cache.get(cache_key), 10)

        # Creating notification should trigger post_save signal and invalidate cache
        Notification.objects.create(
            organization=self.org,
            recipient=self.user,
            title="Cache Test",
            message="Testing signal cache invalidation"
        )
        self.assertIsNone(cache.get(cache_key))

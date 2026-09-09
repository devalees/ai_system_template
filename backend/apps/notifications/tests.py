"""
Unit tests for Universal Notifications Engine data models, preferences, signals, and dispatcher service.
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase

from apps.notifications.dispatcher import NotificationDispatcher
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.signals import get_unread_cache_key
from apps.tenants.models import Organization

User = get_user_model()


class NotificationModelTests(TestCase):
    """Test suite verifying Notification and NotificationPreference models."""

    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        self.user = User.objects.create_user(username="testuser", email="user@example.com", password="password123")
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


class NotificationDispatcherTests(TestCase):
    """Test suite verifying NotificationDispatcher routing, adapters, and unread caching."""

    def setUp(self):
        self.org = Organization.objects.create(name="Dispatcher Org", slug="dispatcher-org")
        self.user = User.objects.create_user(username="recipient", email="recipient@example.com", password="password123")
        self.actor = User.objects.create_user(username="actoruser", password="password123")

    def test_dispatcher_send_in_app(self):
        """Verify sending in-app notification creates database record."""
        results = NotificationDispatcher.send(
            recipient=self.user,
            title="System Alert",
            message="Database maintenance tonight.",
            level=Notification.LEVEL_WARNING,
            actor=self.actor,
            organization=self.org,
            channels=[Notification.CHANNEL_IN_APP]
        )
        self.assertTrue(results.get(Notification.CHANNEL_IN_APP))
        n = Notification.objects.filter(recipient=self.user, title="System Alert").first()
        self.assertIsNotNone(n)
        self.assertEqual(n.level, Notification.LEVEL_WARNING)

    def test_dispatcher_email_adapter(self):
        """Verify EmailAdapter sends email out via Django mail framework."""
        results = NotificationDispatcher.send(
            recipient=self.user,
            title="Welcome Aboard",
            message="Welcome to AI System Template.",
            level=Notification.LEVEL_INFO,
            channels=[Notification.CHANNEL_EMAIL]
        )
        self.assertTrue(results.get(Notification.CHANNEL_EMAIL))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Welcome Aboard", mail.outbox[0].subject)

    @patch("requests.post")
    def test_dispatcher_webhook_and_slack_adapters(self, mock_post):
        """Verify WebhookAdapter and SlackAdapter dispatch HTTP POST requests."""
        mock_post.return_value.status_code = 200

        pref, _ = NotificationPreference.objects.get_or_create(user=self.user)
        pref.webhook_enabled = True
        pref.webhook_url = "https://example.com/webhook"
        pref.slack_enabled = True
        pref.slack_webhook_url = "https://hooks.slack.com/services/XXX"
        pref.save()

        results = NotificationDispatcher.send(
            recipient=self.user,
            title="Webhook & Slack Test",
            message="Testing multi-channel delivery.",
            channels=[Notification.CHANNEL_WEBHOOK, Notification.CHANNEL_SLACK]
        )
        self.assertTrue(results.get(Notification.CHANNEL_WEBHOOK))
        self.assertTrue(results.get(Notification.CHANNEL_SLACK))
        self.assertEqual(mock_post.call_count, 2)

    def test_unread_count_cache_resolution(self):
        """Verify unread count resolution hits cache and queries DB on miss."""
        # Clear cache first
        cache.clear()

        # Create 2 unread notifications
        Notification.objects.create(organization=self.org, recipient=self.user, title="1", message="1")
        Notification.objects.create(organization=self.org, recipient=self.user, title="2", message="2")

        count = NotificationDispatcher.get_unread_count(self.user.id, self.org.id)
        self.assertEqual(count, 2)

        # Check cache is set
        cache_key = get_unread_cache_key(str(self.user.id), str(self.org.id))
        self.assertEqual(cache.get(cache_key), 2)

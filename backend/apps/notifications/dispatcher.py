"""
Dispatcher service layer and multi-channel adapters for Universal Notifications Engine.

Provides:
- NotificationDispatcher: Central dispatcher orchestrating in-app, email, webhook, and Slack delivery.
- Redis-backed unread counter caching helpers.
- Multi-channel adapters.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.signals import get_unread_cache_key

logger = logging.getLogger(__name__)


# ============================================================================
# Multi-Channel Adapters
# ============================================================================

class BaseNotificationAdapter:
    """Base interface for delivery channel adapters."""

    channel_name = "base"

    def deliver(
        self,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        preference: Optional[NotificationPreference] = None,
    ) -> bool:
        """Deliver notification payload via specific adapter channel."""
        raise NotImplementedError


class InAppAdapter(BaseNotificationAdapter):
    """Adapter for internal in-app persistent dashboard notifications."""

    channel_name = Notification.CHANNEL_IN_APP

    def deliver(
        self,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        preference: Optional[NotificationPreference] = None,
    ) -> bool:
        """Create persistent Notification database record."""
        try:
            Notification.objects.create(
                organization=organization,
                recipient=recipient,
                actor=actor,
                level=level,
                title=title,
                message=message,
                action_url=action_url,
                channel=self.channel_name,
                extra_data=extra_data or {},
            )
            return True
        except Exception as e:
            logger.error("InAppAdapter delivery failure for %s: %s", recipient, e)
            return False


class EmailAdapter(BaseNotificationAdapter):
    """Adapter for sending email notifications via Django mail framework."""

    channel_name = Notification.CHANNEL_EMAIL

    def deliver(
        self,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        preference: Optional[NotificationPreference] = None,
    ) -> bool:
        """Send formatted HTML / plain-text email to recipient address."""
        if not recipient.email:
            logger.warning("EmailAdapter skipped: recipient %s has no email address.", recipient)
            return False

        subject = f"[{level.upper()}] {title}"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "notifications@localhost")
        try:
            send_mail(
                subject=subject,
                message=f"{message}\n\nAction URL: {action_url}" if action_url else message,
                from_email=from_email,
                recipient_list=[recipient.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error("EmailAdapter delivery failure to %s: %s", recipient.email, e)
            return False


class WebhookAdapter(BaseNotificationAdapter):
    """Adapter for dispatching JSON webhook payloads to external HTTP endpoints."""

    channel_name = Notification.CHANNEL_WEBHOOK

    def deliver(
        self,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        preference: Optional[NotificationPreference] = None,
    ) -> bool:
        """Post structured JSON payload to configured user or organization webhook endpoint."""
        target_url = preference.webhook_url if preference and preference.webhook_url else None
        if not target_url:
            logger.warning("WebhookAdapter skipped: no target webhook URL configured for user %s.", recipient)
            return False

        payload = {
            "event": "notification.delivered",
            "recipient_id": str(recipient.id),
            "recipient_username": recipient.username,
            "level": level,
            "title": title,
            "message": message,
            "action_url": action_url,
            "organization_id": str(organization.id) if organization else None,
            "extra_data": extra_data or {},
            "timestamp": timezone.now().isoformat(),
        }

        try:
            response = requests.post(target_url, json=payload, timeout=10)
            return response.status_code < 400
        except Exception as e:
            logger.error("WebhookAdapter failed posting to %s: %s", target_url, e)
            return False


class SlackAdapter(BaseNotificationAdapter):
    """Adapter for sending formatted Slack alert messages via incoming webhook."""

    channel_name = Notification.CHANNEL_SLACK

    def deliver(
        self,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        preference: Optional[NotificationPreference] = None,
    ) -> bool:
        """Post Slack block formatting payload to user incoming webhook."""
        slack_url = preference.slack_webhook_url if preference and preference.slack_webhook_url else None
        if not slack_url:
            logger.warning("SlackAdapter skipped: no Slack webhook URL configured for %s.", recipient)
            return False

        emoji = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "🚨"}.get(level, "🔔")
        payload = {
            "text": f"{emoji} *{title}*\n{message}",
            "attachments": [
                {
                    "color": "#36a64f" if level == "success" else ("#ff0000" if level == "error" else "#e67e22"),
                    "fields": [
                        {"title": "Recipient", "value": recipient.username, "short": True},
                        {"title": "Level", "value": level.upper(), "short": True},
                    ],
                }
            ],
        }
        if action_url:
            payload["attachments"][0]["fields"].append({"title": "Action Link", "value": action_url, "short": False})

        try:
            response = requests.post(slack_url, json=payload, timeout=10)
            return response.status_code < 400
        except Exception as e:
            logger.error("SlackAdapter failed posting to Slack: %s", e)
            return False


# ============================================================================
# Central Dispatcher Service & Cache Manager
# ============================================================================

class NotificationDispatcher:
    """
    Central dispatcher managing multi-channel notification routing, preference resolution,
    and Redis unread counter management.
    """

    ADAPTERS = {
        Notification.CHANNEL_IN_APP: InAppAdapter(),
        Notification.CHANNEL_EMAIL: EmailAdapter(),
        Notification.CHANNEL_WEBHOOK: WebhookAdapter(),
        Notification.CHANNEL_SLACK: SlackAdapter(),
    }

    @classmethod
    def get_unread_count(cls, user_id: Any, org_id: Optional[Any] = None) -> int:
        """
        Get unread notification count for a user in a workspace, utilizing Redis cache.
        """
        user_str = str(user_id)
        org_str = str(org_id) if org_id else "global"
        cache_key = get_unread_cache_key(user_str, org_str)

        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return int(cached_count)

        # Cache miss: query database
        qs = Notification.objects.filter(recipient_id=user_id, is_read=False)
        if org_id:
            qs = qs.filter(organization_id=org_id)

        count = qs.count()
        cache.set(cache_key, count, timeout=600)  # 10 minutes cache
        return count

    @classmethod
    def send(
        cls,
        recipient,
        title: str,
        message: str,
        level: str = Notification.LEVEL_INFO,
        actor=None,
        organization=None,
        action_url: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
        async_delivery: bool = True,
    ) -> Dict[str, bool]:
        """
        Orchestrate multi-channel notification delivery to a user recipient.
        """
        # Resolve preferences
        preference, _ = NotificationPreference.objects.get_or_create(user=recipient)

        # Determine target channels
        if channels is None:
            channels = []
            if preference.in_app_enabled:
                channels.append(Notification.CHANNEL_IN_APP)
            if preference.email_enabled:
                channels.append(Notification.CHANNEL_EMAIL)
            if preference.webhook_enabled and preference.webhook_url:
                channels.append(Notification.CHANNEL_WEBHOOK)
            if preference.slack_enabled and preference.slack_webhook_url:
                channels.append(Notification.CHANNEL_SLACK)

        # Fallback: always ensure at least in_app if list is empty
        if not channels:
            channels = [Notification.CHANNEL_IN_APP]

        results = {}
        for ch in channels:
            adapter = cls.ADAPTERS.get(ch)
            if adapter:
                success = adapter.deliver(
                    recipient=recipient,
                    title=title,
                    message=message,
                    level=level,
                    actor=actor,
                    organization=organization,
                    action_url=action_url,
                    extra_data=extra_data,
                    preference=preference,
                )
                results[ch] = success

        return results

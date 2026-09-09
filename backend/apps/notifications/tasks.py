"""
Celery asynchronous tasks for Universal Notifications Engine.

Provides:
- send_notification_async_task: Main background task for multi-channel notification dispatch.
- send_email_notification_async_task: Dedicated background email dispatcher with retry logic.
- send_webhook_notification_async_task: Dedicated background HTTP webhook poster with retry logic.
"""

import logging
from typing import Any, Dict, List, Optional

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.notifications.dispatcher import NotificationDispatcher
from apps.notifications.models import Notification
from apps.tenants.models import Organization

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def send_notification_async_task(
    self,
    recipient_id: str,
    title: str,
    message: str,
    level: str = Notification.LEVEL_INFO,
    actor_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    action_url: str = "",
    extra_data: Optional[Dict[str, Any]] = None,
    channels: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    Asynchronous Celery task orchestrating multi-channel notification dispatch.
    """
    try:
        recipient = User.objects.get(id=recipient_id)
    except User.DoesNotExist:
        logger.error("send_notification_async_task aborted: User recipient %s not found.", recipient_id)
        return {}

    actor = User.objects.filter(id=actor_id).first() if actor_id else None
    organization = Organization.objects.filter(id=organization_id).first() if organization_id else None

    try:
        results = NotificationDispatcher.send(
            recipient=recipient,
            title=title,
            message=message,
            level=level,
            actor=actor,
            organization=organization,
            action_url=action_url,
            extra_data=extra_data,
            channels=channels,
            async_delivery=False,
        )
        return results
    except Exception as exc:
        logger.warning("send_notification_async_task failed, retrying... (%s)", exc)
        raise self.retry(exc=exc)

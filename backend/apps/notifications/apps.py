"""
App configuration for Universal Notifications Engine (apps.notifications).
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotificationsConfig(AppConfig):
    """AppConfig registering notifications app and bootstrapping signals."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = _("Notifications Engine")

    def ready(self):
        """Import signal handlers on application readiness."""
        try:
            import apps.notifications.signals  # noqa: F401
        except ImportError:
            pass

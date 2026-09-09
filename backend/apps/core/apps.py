from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    """Configuration for the core foundation, abstract models, and dynamic settings app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = _('Core & System Configuration')

    def ready(self):
        """Perform runtime initialization for core signals and settings."""
        try:
            from apps.core import signals  # noqa: F401
        except ImportError:
            pass

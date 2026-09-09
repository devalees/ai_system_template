"""
App configuration for Universal Document & Media Management (apps.media).
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MediaConfig(AppConfig):
    """AppConfig registering media app."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    verbose_name = _("Document & Media Management")

"""
Application Configuration for Dynamic Visual Reporting Engine.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AppsReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reports"
    verbose_name = _("Reports & Documents Engine")

    def ready(self):
        """
        Bootstrap automation actions and settings for reports engine.
        """
        try:
            from apps.reports.actions import register_report_actions
            register_report_actions()
        except ImportError:
            pass

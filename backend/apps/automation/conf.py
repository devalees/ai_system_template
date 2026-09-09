"""
Automation Engine Settings Registration.
"""

from django.utils.translation import gettext_lazy as _
from apps.core.settings_registry import Setting, register_settings_group


@register_settings_group(
    app_label="automation",
    verbose_name=_("Automation Engine"),
    icon="⚡",
    order=20
)
class AutomationSettings:
    HERMES_REQUEST_TIMEOUT = Setting(
        data_type="int",
        default=120,
        verbose_name=_("Hermes Request Timeout (seconds)"),
        help_text=_("Maximum HTTP wait time for Hermes Agent task completion.")
    )
    DEFAULT_AUTO_RETRY = Setting(
        data_type="bool",
        default=True,
        verbose_name=_("Auto-Retry Failed Actions"),
        help_text=_("Automatically re-queue failed Celery automation tasks.")
    )
    MAX_RETRY_COUNT = Setting(
        data_type="int",
        default=3,
        verbose_name=_("Max Task Retries"),
        help_text=_("Maximum retry attempts before permanently failing an automation action.")
    )
    DEFAULT_EXECUTION_MODE = Setting(
        data_type="choice",
        default="async",
        choices=[("async", _("Asynchronous (Celery)")), ("sync", _("Synchronous (Direct)"))],
        verbose_name=_("Default Execution Mode"),
        help_text=_("Execution dispatch strategy for automated action pipelines.")
    )

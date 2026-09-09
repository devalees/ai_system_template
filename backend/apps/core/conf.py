"""
General Platform Settings Registration.
"""

from django.utils.translation import gettext_lazy as _
from apps.core.settings_registry import Setting, register_settings_group


@register_settings_group(
    app_label="general",
    verbose_name=_("General Platform"),
    icon="⚙️",
    order=10
)
class GeneralSettings:
    SITE_NAME = Setting(
        data_type="str",
        default="AI System Platform",
        verbose_name=_("Platform Title"),
        help_text=_("Public title displayed in navigation, admin headers, and communications.")
    )
    MAINTENANCE_MODE = Setting(
        data_type="bool",
        default=False,
        verbose_name=_("Maintenance Mode"),
        help_text=_("When enabled, restricts access for non-administrative users.")
    )
    DEFAULT_CURRENCY = Setting(
        data_type="choice",
        default="USD",
        choices=[("USD", "USD ($)"), ("EUR", "EUR (€)"), ("SAR", "SAR (﷼)"), ("AED", "AED (د.إ)")],
        verbose_name=_("Default Currency"),
        help_text=_("Base currency used across financial calculations and token accounting.")
    )
    ITEMS_PER_PAGE = Setting(
        data_type="int",
        default=25,
        verbose_name=_("Default Page Size"),
        help_text=_("Number of records displayed per page across data tables.")
    )

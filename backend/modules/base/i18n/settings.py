"""Multi-Language & Localization Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class I18nSettings(BaseModel):
    """Configurable tenant-level language, localization, and text direction preferences."""

    default_locale: str = Field(
        default="en",
        title="Default System Language",
        description="Fallback display language for this organization when user preference is not set.",
        json_schema_extra={
            "category": "Localization",
            "options": [
                {"value": "en", "label": "English"},
                {"value": "ar", "label": "Arabic (العربية)"}
            ]
        }
    )
    rtl_mode: str = Field(
        default="auto",
        title="Script Direction Mode",
        description="Layout and text reading direction for user interfaces.",
        json_schema_extra={
            "category": "Localization",
            "options": [
                {"value": "auto", "label": "Automatic (Based on Active Locale)"},
                {"value": "ltr", "label": "Left-to-Right (LTR)"},
                {"value": "rtl", "label": "Right-to-Left (RTL)"}
            ]
        }
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("i18n", I18nSettings)

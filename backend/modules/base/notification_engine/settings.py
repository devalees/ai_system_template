"""Multi-Channel Notification Engine Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class NotificationSettings(BaseModel):
    """Configurable tenant-level multi-channel notification policies."""

    enable_in_app: bool = Field(
        default=True,
        title="In-App Notifications",
        description="Deliver real-time alerts inside user web and mobile application sessions.",
        json_schema_extra={"category": "Notification Channels"}
    )
    enable_webpush: bool = Field(
        default=True,
        title="WebPush Browser Notifications",
        description="Deliver push notifications to registered browser endpoints via VAPID.",
        json_schema_extra={"category": "Notification Channels"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("notification_engine", NotificationSettings)

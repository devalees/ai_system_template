"""Mail Gateway & Async Email Pipeline Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class MailGatewaySettings(BaseModel):
    """Configurable tenant-level outbound email policies and defaults."""

    default_from_name: str = Field(
        default="Sovereign Platform",
        title="Default Sender Name",
        description="Display name shown in the 'From' header of outgoing system emails.",
        json_schema_extra={"category": "Email Configuration"}
    )
    default_from_email: str = Field(
        default="notifications@sovereign.local",
        title="Default Sender Email",
        description="Email address used as the sender when email templates do not override it.",
        json_schema_extra={"category": "Email Configuration"}
    )
    max_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        title="Max Delivery Retries",
        description="Maximum times the background worker retries failed outbound email delivery.",
        json_schema_extra={"category": "Delivery & Queuing"}
    )
    async_dispatch_enabled: bool = Field(
        default=True,
        title="Async Background Dispatch",
        description="Enqueue outbound emails into Celery background workers rather than sending synchronously.",
        json_schema_extra={"category": "Delivery & Queuing"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("mail_gateway", MailGatewaySettings)

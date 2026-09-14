"""Identity & Access Management (RBAC) Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class IdentitySettings(BaseModel):
    """Configurable tenant-level security and authentication policies."""

    allow_registration: bool = Field(
        default=False,
        title="Allow Public Self-Registration",
        description="Allow external users to create accounts without prior administrator invitation.",
        json_schema_extra={"category": "User Onboarding"}
    )
    enforce_2fa: bool = Field(
        default=False,
        title="Enforce Two-Factor Authentication (2FA)",
        description="Require all users within this organization to enable 2FA before accessing system resources.",
        json_schema_extra={"category": "Security & Authentication"}
    )
    password_min_length: int = Field(
        default=8,
        ge=6,
        le=128,
        title="Minimum Password Length",
        description="Minimum number of characters required for user passwords.",
        json_schema_extra={"category": "Security & Authentication"}
    )
    session_expiry_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        title="Session Token Expiry (Hours)",
        description="Duration in hours for which user authentication tokens remain valid.",
        json_schema_extra={"category": "Security & Authentication"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("identity_rbac", IdentitySettings)

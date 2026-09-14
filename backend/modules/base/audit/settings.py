"""Immutable Audit Trail Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class AuditSettings(BaseModel):
    """Configurable tenant-level compliance and audit log retention policies."""

    retention_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        title="Audit Log Retention (Days)",
        description="Number of days before immutable audit records and diffs become eligible for archive purging.",
        json_schema_extra={"category": "Compliance & Retention"}
    )
    log_read_operations: bool = Field(
        default=False,
        title="Log Read Operations",
        description="Record audit entries for read queries in addition to standard data mutations.",
        json_schema_extra={"category": "Compliance & Retention"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("audit", AuditSettings)

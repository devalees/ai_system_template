"""Unified Atomic Backup & Archive Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class BackupSettings(BaseModel):
    """Configurable tenant-level disaster recovery and backup retention policies."""

    retention_count: int = Field(
        default=5,
        ge=1,
        le=100,
        title="Backup Archive Retention Limit",
        description="Maximum number of historical backup archives retained before automatic rotation.",
        json_schema_extra={"category": "Backup & Disaster Recovery"}
    )
    auto_backup_enabled: bool = Field(
        default=False,
        title="Automated Scheduled Backups",
        description="Automatically trigger atomic backup archive generation daily via Celery Beat.",
        json_schema_extra={"category": "Backup & Disaster Recovery"}
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("backup", BackupSettings)

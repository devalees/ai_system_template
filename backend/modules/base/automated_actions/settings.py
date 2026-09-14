"""Automated Actions & Event-Driven TCA Subsystem Module Settings Definition."""

from pydantic import BaseModel, Field
from modules.base.settings.service import SettingsService


class AutomatedActionsSettings(BaseModel):
    """Configurable tenant-level TCA automation policies and safety thresholds."""

    enable_automation: bool = Field(
        default=True,
        title="Enable Automation Engine",
        description="Master switch to activate or pause event-driven automated action execution for the tenant.",
        json_schema_extra={"category": "Engine Controls"},
    )
    max_action_depth: int = Field(
        default=5,
        ge=1,
        le=20,
        title="Max Cascade Depth Limit",
        description="Maximum cascading action execution depth to prevent infinite recursive mutation loops.",
        json_schema_extra={"category": "Safety & Loop Prevention"},
    )
    async_execution_enabled: bool = Field(
        default=True,
        title="Async Celery Offloading",
        description="Offload I/O-heavy action handlers (emails, notifications, webhooks) to Celery background workers.",
        json_schema_extra={"category": "Execution Pipeline"},
    )
    log_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        title="Audit Log Retention (Days)",
        description="Number of days to preserve action execution telemetry logs before periodic pruning.",
        json_schema_extra={"category": "Audit & Observability"},
    )
    log_successful_runs: bool = Field(
        default=True,
        title="Log Successful Executions",
        description="Record detailed execution logs for successful action executions in addition to failures.",
        json_schema_extra={"category": "Audit & Observability"},
    )


# Auto-register settings schema with SettingsService
SettingsService.register_module_settings("automated_actions", AutomatedActionsSettings)

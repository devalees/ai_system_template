"""
Data Models for Centralized Automation Engine.
"""

from django.db import models
from django.utils import timezone
from .registry import CATEGORY_CHOICES


TRIGGER_TYPE_CHOICES = [
    ('model_event', '📦 Model Event (CRUD)'),
    ('time_based', '⏱️ Time-Based Schedule'),
    ('webhook', '🌐 Inbound Webhook'),
    ('manual', '▶️ Manual Only'),
]

EXECUTION_MODE_CHOICES = [
    ('recurring', '🔁 Recurring'),
    ('once', '⚡ Once (One-Shot)'),
]

EVENT_TYPE_CHOICES = [
    ('created', 'Created (Insert)'),
    ('updated', 'Updated (Edit)'),
    ('deleted', 'Deleted'),
    ('any', 'Any Change'),
]

SCHEDULE_UNIT_CHOICES = [
    ('seconds', 'Seconds'),
    ('minutes', 'Minutes'),
    ('hours', 'Hours'),
    ('days', 'Days'),
    ('weeks', 'Weeks'),
    ('months', 'Months'),
]

LOG_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('running', 'Running'),
    ('success', 'Success'),
    ('failed', 'Failed'),
]


class AutomationRule(models.Model):
    """
    Configurable Automation Rule linking Triggers to Registered Actions.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Unique descriptive name for the automation rule.")
    description = models.TextField(blank=True, help_text="Detailed purpose and behavior notes.")
    is_active = models.BooleanField(
        default=True,
        help_text="Active toggle: uncheck to pause this rule without deleting it."
    )

    # Trigger Configuration
    trigger_type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPE_CHOICES,
        default='model_event',
        help_text="Whether this rule fires on database events, periodic timers, or webhooks."
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODE_CHOICES,
        default='recurring',
        help_text="'once' automatically deactivates the rule after a single successful run."
    )
    target_model = models.CharField(
        max_length=150,
        blank=True,
        help_text="Django model to watch, e.g. 'auth.User' or 'integration.AgentTask'."
    )
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        default='created',
        blank=True,
        help_text="CRUD lifecycle event that triggers the action."
    )
    filter_conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON criteria required for trigger match, e.g. {'is_agent': true} or {'status': 'completed'}."
    )

    # Time-Based Scheduling Configuration (Celery Beat)
    schedule_unit = models.CharField(
        max_length=20,
        choices=SCHEDULE_UNIT_CHOICES,
        default='minutes',
        blank=True,
        help_text="Time scale unit for periodic executions."
    )
    schedule_value = models.PositiveIntegerField(
        default=5,
        null=True,
        blank=True,
        help_text="Frequency interval number (e.g. 5 for every 5 minutes)."
    )
    scheduled_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Target timestamp for one-shot scheduled execution."
    )
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_rule',
        help_text="Linked Celery Beat periodic task instance."
    )

    # Metrics & State
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)

    # Action Configuration
    action_category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='internal_app',
        help_text="Category of the target service."
    )
    action_type = models.CharField(
        max_length=150,
        help_text="Identifier of the registered action handler (e.g. 'provision_hermes_profile')."
    )
    action_params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Static parameters or configuration dictionary passed to the action handler."
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 1. Connect targeted model signals if model_event
        if self.is_active and self.trigger_type == 'model_event' and self.target_model:
            try:
                from django.apps import apps
                from .signals import connect_model_signals
                model_cls = apps.get_model(self.target_model)
                if model_cls:
                    connect_model_signals(model_cls)
            except Exception:
                pass

        # 2. Synchronize with Celery Beat periodic task if time_based
        try:
            from .scheduler import sync_rule_to_celery_beat
            sync_rule_to_celery_beat(self)
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        try:
            from .scheduler import delete_rule_periodic_task
            delete_rule_periodic_task(self)
        except Exception:
            pass
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Automation Rule"
        verbose_name_plural = "Automation Rules"

    def __str__(self) -> str:
        status_icon = "🟢" if self.is_active else "⏸️"
        return f"{status_icon} {self.name} [{self.get_trigger_type_display()}]"


class AutomationLog(models.Model):
    """
    Execution and audit log for automated actions.
    """
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    trigger_source = models.CharField(
        max_length=255,
        help_text="Contextual description of the event that triggered execution."
    )
    status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default='pending'
    )
    input_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payload / model snapshot at the moment of trigger."
    )
    output_result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Return data from the executed action."
    )
    error_message = models.TextField(
        blank=True,
        help_text="Exception trace or failure message if execution failed."
    )
    duration_ms = models.IntegerField(
        default=0,
        help_text="Execution duration in milliseconds."
    )
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-executed_at']
        verbose_name = "Automation Log"
        verbose_name_plural = "Automation Logs"

    def __str__(self) -> str:
        icon = "✓" if self.status == "success" else ("✗" if self.status == "failed" else "⏳")
        rule_name = self.rule.name if self.rule else "Ad-Hoc"
        return f"[{icon} {self.status.upper()}] {rule_name} @ {self.executed_at.strftime('%Y-%m-%d %H:%M:%S')}"

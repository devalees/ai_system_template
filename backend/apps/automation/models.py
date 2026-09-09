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
    ('field_changed', 'Field Changed / State Transition'),
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


TARGET_OPERATION_CHOICES = [
    ('create', '➕ Create New Record'),
    ('update', '✏️ Update Existing Record'),
    ('delete', '🗑️ Delete Record'),
]


class AutomationTrigger(models.Model):
    """
    Defines WHEN an automation workflow fires (Model Events, Schedules, Webhooks, Manual).
    Serves as the root event for 1-to-N sequenced AutomationActions.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Unique descriptive name for the trigger event.")
    description = models.TextField(blank=True, help_text="Detailed purpose and trigger behavior notes.")
    is_active = models.BooleanField(
        default=True,
        help_text="Active toggle: uncheck to pause this trigger and its actions without deleting it."
    )
    is_system = models.BooleanField(
        default=False,
        help_text="System-level trigger protecting core workflows from deletion."
    )

    # Trigger Configuration (Source Event)
    trigger_type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPE_CHOICES,
        default='model_event',
        help_text="Whether this trigger fires on database events, periodic timers, or webhooks."
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODE_CHOICES,
        default='recurring',
        help_text="'once' automatically deactivates the trigger after a single successful execution pipeline."
    )
    trigger_model = models.CharField(
        max_length=150,
        blank=True,
        help_text="Source Django model to watch for events, e.g. 'auth.User' or 'integration.AgentTask'."
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
    condition_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured Odoo-style visual filter rules: [{'field': 'status', 'operator': '==', 'value': 'completed'}]."
    )

    # State Transition & Field Change Configuration (Odoo-Style)
    trigger_field = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specific field to monitor for changes (e.g. 'status', 'review_verdict', 'cost_usd')."
    )
    previous_value = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional previous value before change (e.g. 'review' or 'draft')."
    )
    target_value = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional target value after change (e.g. 'completed' or 'approved')."
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
        related_name='automation_trigger',
        help_text="Linked Celery Beat periodic task instance."
    )

    # Metrics & State
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 1. Connect targeted model signals if model_event
        if self.is_active and self.trigger_type == 'model_event' and self.trigger_model:
            try:
                from django.apps import apps
                from .signals import connect_model_signals
                model_cls = apps.get_model(self.trigger_model)
                if model_cls:
                    connect_model_signals(model_cls)
            except Exception:
                pass

        # 2. Synchronize with Celery Beat periodic task if time_based
        try:
            from .scheduler import sync_trigger_to_celery_beat
            sync_trigger_to_celery_beat(self)
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        if self.is_system:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"System automation trigger '{self.name}' is protected and cannot be deleted.")
        try:
            from .scheduler import delete_trigger_periodic_task
            delete_trigger_periodic_task(self)
        except Exception:
            pass
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Automation Trigger"
        verbose_name_plural = "Automation Triggers"

    def __str__(self) -> str:
        status_icon = "🟢" if self.is_active else "⏸️"
        return f"{status_icon} {self.name} [{self.get_trigger_type_display()}]"


class AutomationAction(models.Model):
    """
    Executable action step attached to an AutomationTrigger.
    Multiple actions can be linked to a single trigger and execute in sequential order.
    """
    trigger = models.ForeignKey(
        AutomationTrigger,
        on_delete=models.CASCADE,
        related_name='actions',
        help_text="Parent trigger event that activates this action."
    )
    name = models.CharField(max_length=200, help_text="Descriptive title of the action step.")
    description = models.TextField(blank=True, help_text="Detailed action behavior notes.")
    sequence = models.PositiveIntegerField(
        default=10,
        help_text="Execution order among actions attached to the same trigger (e.g. 10, 20, 30)."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active toggle: uncheck to pause this specific action without deleting it."
    )
    is_system = models.BooleanField(
        default=False,
        help_text="Protected system action that cannot be deleted."
    )

    # Target Model Record CRUD & Field Mapping (Destination)
    target_model = models.CharField(
        max_length=150,
        blank=True,
        help_text="Destination Django model for CRUD record operations, e.g. 'integration.AgentTask'."
    )
    target_operation = models.CharField(
        max_length=50,
        choices=TARGET_OPERATION_CHOICES,
        default='',
        blank=True,
        help_text="CRUD operation to execute on the target model ('create', 'update', 'delete')."
    )
    field_mappings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of target model fields to values or context expressions, e.g. {'title': '{{task_title}}'}."
    )

    # Registered Service Handler
    action_category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='internal_app',
        help_text="Category of the target service."
    )
    action_type = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text="Identifier of the registered action handler (e.g. 'provision_hermes_profile')."
    )
    action_params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Static parameters or configuration dictionary passed to the action handler."
    )

    # Metrics & State
    last_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        if self.is_system:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"System automation action '{self.name}' is protected and cannot be deleted.")
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['sequence', 'created_at']
        verbose_name = "Automation Action"
        verbose_name_plural = "Automation Actions"

    def __str__(self) -> str:
        status_icon = "🟢" if self.is_active else "⏸️"
        return f"{status_icon} [{self.sequence}] {self.name} ({self.get_action_category_display()})"


# Backward-compatibility alias during refactoring
AutomationRule = AutomationTrigger


class AutomationLog(models.Model):
    """
    Execution and audit log for automated actions.
    """
    trigger = models.ForeignKey(
        AutomationTrigger,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Parent trigger event that initiated execution."
    )
    action = models.ForeignKey(
        AutomationAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Specific action step that was executed."
    )
    # Kept for backward compatibility with legacy references
    rule = models.ForeignKey(
        'AutomationTrigger',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_logs'
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
        action_name = self.action.name if self.action else (self.trigger.name if self.trigger else "Ad-Hoc")
        return f"[{icon} {self.status.upper()}] {action_name} @ {self.executed_at.strftime('%Y-%m-%d %H:%M:%S')}"

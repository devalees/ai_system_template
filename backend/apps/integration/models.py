import uuid
from django.db import models
from django.contrib.auth.models import User

class HandshakeLog(models.Model):
    """
    Records bidirectional connectivity and handshakes between
    external agent runtimes (e.g., Hermes) and the Django backend.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_id = models.CharField(max_length=120, default='hermes-agent')
    version = models.CharField(max_length=60, blank=True, default='unknown')
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    server_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Handshake Log'
        verbose_name_plural = 'Handshake Logs'

    def __str__(self):
        return f"{self.agent_id} ({self.status}) @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class AgentProfile(models.Model):
    """
    Registry of configured Hermes Agent Profiles (digital employees).
    """
    ROLE_CHOICES = [
        ('orchestrator', 'Orchestrator / Chief of Staff'),
        ('finance', 'Finance & Cost Control'),
        ('quality_assurance', 'Quality Assurance & Audit'),
        ('communications', 'Communications & Client Relations'),
        ('knowledge_management', 'Knowledge Management & Documentation'),
        ('general', 'General / Custom'),
    ]

    REASONING_EFFORT_CHOICES = [
        ('none', 'None (Disabled)'),
        ('low', 'Low (Fast / Minimal Cost)'),
        ('medium', 'Medium (Balanced Default)'),
        ('high', 'High (Deep Reasoning / Strict QA)'),
        ('max', 'Max (Frontier Reasoning Budget)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True, help_text="Hermes profile slug (e.g., cost_controller)")
    display_name = models.CharField(max_length=120)
    role = models.CharField(max_length=60, choices=ROLE_CHOICES, default='general')
    description = models.TextField(blank=True)
    model_name = models.CharField(max_length=120, default='google/gemini-2.5-flash')
    provider = models.CharField(max_length=60, default='openrouter')
    reasoning_effort = models.CharField(
        max_length=20,
        choices=REASONING_EFFORT_CHOICES,
        default='medium',
        help_text="Reasoning/thinking effort level passed to Hermes Agent runtime (none, low, medium, high, max).",
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='agent_profile',
        help_text="Underlying Django service account / bot user for RBAC and API authentication."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Agent Profile'
        verbose_name_plural = 'Agent Profiles'

    def __str__(self):
        return f"{self.display_name} ({self.name})"


class SpendReport(models.Model):
    """
    Records token consumption and expenditure reports pushed by the cost_controller profile.
    """
    STATUS_CHOICES = [
        ('OK', 'Within Budget'),
        ('WARNING', 'Approaching Limit'),
        ('EXCEEDED', 'Budget Exceeded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(AgentProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='spend_reports')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_spend_reports',
        help_text="User/bot account that submitted this spend report."
    )
    reported_by = models.CharField(max_length=64, default='cost_controller')
    total_api_calls = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveBigIntegerField(default=0)
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    daily_budget_usd = models.DecimalField(max_digits=10, decimal_places=2, default=10.0)
    budget_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OK')
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Spend Report'
        verbose_name_plural = 'Spend Reports'

    def __str__(self):
        return f"Spend ${self.total_cost_usd} USD [{self.budget_status}] @ {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class AgentTask(models.Model):
    """
    Represents a task dispatched to or executed by an agent profile.
    Supports implementer -> reviewer verification lifecycle.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    VERDICT_CHOICES = [
        ('approved', 'Approved'),
        ('changes_requested', 'Changes Requested'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=120, default='hermes-agent')
    assigned_profile = models.ForeignKey(AgentProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_agent_tasks',
        help_text="User/bot account that created this task."
    )
    task_name = models.CharField(max_length=200)
    input_payload = models.JSONField(default=dict, blank=True)
    output_result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    review_verdict = models.CharField(max_length=30, choices=VERDICT_CHOICES, blank=True, default='')
    reviewer_notes = models.TextField(blank=True, default='')
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0.0)
    tokens_used = models.PositiveIntegerField(default=0)
    reasoning_effort = models.CharField(
        max_length=20,
        choices=AgentProfile.REASONING_EFFORT_CHOICES + [('inherit', 'Inherit from Profile')],
        default='inherit',
        help_text="Task-specific reasoning effort override, or inherit from profile.",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Agent Task'
        verbose_name_plural = 'Agent Tasks'

    def __str__(self):
        profile_label = self.assigned_profile.name if self.assigned_profile else self.agent_name
        return f"[{self.status.upper()}] {self.task_name} ({profile_label})"

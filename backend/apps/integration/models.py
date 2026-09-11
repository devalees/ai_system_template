import uuid
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import AuditableModel, TimeStampedModel

class HandshakeLog(TimeStampedModel):
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

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Handshake Log'
        verbose_name_plural = 'Handshake Logs'

    def __str__(self):
        return f"{self.agent_id} ({self.status}) @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"



class ProviderCredential(AuditableModel):
    """
    Stores encrypted LLM inference provider credentials and custom endpoints.
    Supports system-wide defaults and multi-tenant workspace isolation.
    """
    PROVIDER_CHOICES = [
        ('openrouter', 'OpenRouter'),
        ('gemini', 'Google Gemini'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('groq', 'Groq'),
        ('deepseek', 'DeepSeek'),
        ('custom', 'Custom / OpenAI-Compatible Endpoint'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        help_text="Display label for this credential (e.g., 'Primary OpenRouter', 'Gemini Flash Tier')."
    )
    provider_type = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default='openrouter',
        db_index=True,
        help_text="Underlying LLM provider service."
    )
    encrypted_api_key = models.TextField(
        blank=True,
        default="",
        help_text="Encrypted API key stored securely at rest."
    )
    base_url = models.URLField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional custom API base URL (e.g. https://openrouter.ai/api/v1, or local Ollama/vLLM)."
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this provider credential can be used for inference."
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates this credential as the default for its provider type."
    )
    organization = models.ForeignKey(
        'tenants.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provider_credentials',
        help_text="Optional workspace scoping for multi-tenant isolation."
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom provider parameters, default headers, or rate limits."
    )

    class Meta:
        ordering = ['provider_type', '-is_default', 'name']
        verbose_name = 'Provider Credential'
        verbose_name_plural = 'Provider Credentials'

    @property
    def api_key(self) -> str:
        """Decrypts and returns the plaintext API key."""
        from apps.core.crypto import decrypt_secret
        return decrypt_secret(self.encrypted_api_key)

    @api_key.setter
    def api_key(self, value: str) -> None:
        """Encrypts plaintext API key before assigning to storage field."""
        from apps.core.crypto import encrypt_secret
        self.encrypted_api_key = encrypt_secret(value.strip()) if value else ""

    @property
    def masked_key(self) -> str:
        """Returns a masked representation of the API key for secure display."""
        from apps.core.crypto import mask_secret
        plain = self.api_key
        return mask_secret(plain) if plain else "—"

    def save(self, *args, **kwargs):
        """Enforces a single active default per provider_type and organization."""
        if self.is_default:
            qs = ProviderCredential.objects.filter(
                provider_type=self.provider_type,
                organization=self.organization,
                is_default=True
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            qs.update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        default_tag = " [DEFAULT]" if self.is_default else ""
        return f"{self.name} ({self.get_provider_type_display()}){default_tag}"


class Profile(AuditableModel):
    """
    Unified User Profile attached 1-to-1 to Django's auth.User.
    Accommodates human staff, autonomous AI agent service accounts, and external clients.
    """
    USER_TYPE_CHOICES = [
        ('human', 'Human User / Staff'),
        ('agent', 'AI Agent Service Account'),
        ('client', 'External Client / Customer'),
    ]

    ROLE_CHOICES = [
        ('orchestrator', 'Orchestrator / Chief of Staff'),
        ('finance', 'Finance & Cost Control'),
        ('quality_assurance', 'Quality Assurance & Audit'),
        ('communications', 'Client Service & Communications'),
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
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='profile',
        help_text="Underlying Django auth.User."
    )
    is_agent = models.BooleanField(
        default=False,
        help_text="Designates whether this user operates as an AI Agent."
    )
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='human',
        help_text="User classification across the ecosystem."
    )
    name = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Profile identifier / alias."
    )
    hermes_profile_name = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Hermes engine profile folder/slug (e.g., cost_controller)."
    )
    display_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=60, choices=ROLE_CHOICES, default='general', blank=True)
    description = models.TextField(blank=True)
    model_name = models.CharField(max_length=120, default='google/gemini-2.5-flash')
    provider = models.CharField(max_length=60, default='openrouter')
    provider_credential = models.ForeignKey(
        ProviderCredential,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profiles',
        help_text="Optional override: Leave blank to automatically use the default credential for the selected provider. Specify only for dedicated keys or custom endpoints (e.g. Ollama/vLLM)."
    )
    reasoning_effort = models.CharField(
        max_length=20,
        choices=REASONING_EFFORT_CHOICES,
        default='medium',
        help_text="Reasoning/thinking effort level passed to Hermes Agent runtime (none, low, medium, high, max).",
    )
    is_active = models.BooleanField(default=True)
    preferred_language = models.CharField(
        max_length=10,
        choices=[('en', 'English'), ('ar', 'العربية')],
        default='en',
        help_text="User interface language preference (en / ar)."
    )
    ai_budget_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=15.00,
        help_text="Allocated AI assistance dollar budget for this client engagement."
    )
    ai_spend_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        help_text="Cumulative LLM spend consumed by this client in USD."
    )

    @property
    def ai_budget_percentage(self) -> float:
        """Returns the percentage of the AI budget consumed (0.0 - 100.0+)."""
        if not self.ai_budget_usd or float(self.ai_budget_usd) <= 0:
            return 0.0
        pct = (float(self.ai_spend_usd) / float(self.ai_budget_usd)) * 100.0
        return round(pct, 2)

    @property
    def ai_budget_status(self) -> str:
        """
        Calculates milestone status:
        - 'OK': 0.0% - 74.99%
        - 'WARNING_75': 75.0% - 99.99%
        - 'EXCEEDED_100': >= 100.0%
        """
        pct = self.ai_budget_percentage
        if pct >= 100.0:
            return 'EXCEEDED_100'
        elif pct >= 75.0:
            return 'WARNING_75'
        return 'OK'


    class Meta:
        ordering = ['user__username', 'created_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def resolve_provider_and_key(self):
        """
        Resolves the active LLM provider, plaintext API key, and base URL for this profile.
        Hierarchy:
          1. Directly assigned ProviderCredential (if active)
          2. Default active ProviderCredential for self.provider
          3. Fallback to settings.py or process environment variables (e.g. OPENROUTER_API_KEY)
        Returns:
          tuple: (provider_name: str, api_key: str, base_url: str)
        """
        # 1. Directly assigned credential
        if self.provider_credential and self.provider_credential.is_active:
            return (
                self.provider_credential.provider_type,
                self.provider_credential.api_key,
                self.provider_credential.base_url or ""
            )

        # 2. Default active ProviderCredential matching self.provider
        target_provider = self.provider or "openrouter"
        default_cred = ProviderCredential.objects.filter(
            provider_type=target_provider,
            is_active=True,
            is_default=True
        ).first()
        if not default_cred:
            default_cred = ProviderCredential.objects.filter(
                provider_type=target_provider,
                is_active=True
            ).first()

        if default_cred and default_cred.api_key:
            return (default_cred.provider_type, default_cred.api_key, default_cred.base_url or "")

        # 3. Fallback to settings.py / environment
        from django.conf import settings
        import os
        setting_key = f"{target_provider.upper()}_API_KEY"
        env_fallback = getattr(settings, setting_key, "") or os.environ.get(setting_key, "") or getattr(settings, f"{target_provider.upper()}_KEY", "")
        return (target_provider, str(env_fallback) if env_fallback else "", "")

    def save(self, *args, **kwargs):
        if not self.hermes_profile_name and self.name:
            self.hermes_profile_name = self.name
        if not self.name:
            self.name = self.hermes_profile_name or (self.user.username if self.user else '')
        if not self.display_name:
            self.display_name = self.name.replace('_', ' ').title() if self.name else ''
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.display_name or (self.user.username if self.user else str(self.id))
        if self.is_agent:
            return f"🤖 {label} ({self.hermes_profile_name or self.name or 'Agent'})"
        return f"👤 {label} ({self.get_user_type_display()})"


# Backward-compatible alias
AgentProfile = Profile
User.agent_profile = property(lambda u: getattr(u, 'profile', None))




class SpendReport(AuditableModel):
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
    client_profile = models.ForeignKey(
        'Profile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_spend_reports',
        help_text="Optional client profile associated with this spend report."
    )
    reported_by = models.CharField(max_length=64, default='cost_controller')

    total_api_calls = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveBigIntegerField(default=0)
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    daily_budget_usd = models.DecimalField(max_digits=10, decimal_places=2, default=10.0)
    budget_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OK')
    recommendations = models.JSONField(
        default=list,
        blank=True,
        help_text="Cost efficiency and model optimization recommendations generated during spend audit."
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Spend Report'
        verbose_name_plural = 'Spend Reports'

    def __str__(self):
        return f"Spend ${self.total_cost_usd} USD [{self.budget_status}] @ {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ModelBenchmark(AuditableModel):
    """
    Stores frontier AI model benchmark scores (e.g. DeepSWE, SWE-bench) and task efficiency metrics.
    Used by Cost Controller and Orchestrator to evaluate Intelligence-per-Dollar ROI.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_identifier = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Full model identifier (e.g. google/gemini-2.5-flash, anthropic/claude-3-5-sonnet)."
    )
    benchmark_name = models.CharField(
        max_length=60,
        default='DeepSWE',
        db_index=True,
        help_text="Name of benchmark suite (e.g. DeepSWE, SWE-bench)."
    )
    score = models.FloatField(
        help_text="Primary benchmark pass rate / score percentage (0.0 - 100.0)."
    )
    avg_cost_per_task = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Measured average cost per benchmark task in USD."
    )
    tokens_per_task = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average output or total tokens per task."
    )
    agent_steps = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Average agent reasoning/tool steps per task."
    )
    source_url = models.URLField(
        default='https://deepswe.datacurve.ai/',
        blank=True,
        help_text="Origin leaderboard or reference URL."
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional benchmark dimensions (context window, framework, raw metrics)."
    )
    last_synced_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when benchmark record was last updated."
    )

    class Meta:
        ordering = ['-score', 'avg_cost_per_task']
        unique_together = [('model_identifier', 'benchmark_name')]
        verbose_name = 'Model Benchmark'
        verbose_name_plural = 'Model Benchmarks'

    def __str__(self):
        return f"{self.model_identifier} — {self.benchmark_name}: {self.score}%"


class AgentTask(AuditableModel):
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

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Agent Task'
        verbose_name_plural = 'Agent Tasks'

    def __str__(self):
        profile_label = self.assigned_profile.name if self.assigned_profile else self.agent_name
        return f"[{self.status.upper()}] {self.task_name} ({profile_label})"

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import HandshakeLog, Profile, SpendReport, AgentTask, ProviderCredential, ModelBenchmark
from .forms import ProfileAdminForm, ProviderCredentialAdminForm


class ProfileInline(admin.StackedInline):
    """
    Embeds Profile configuration directly inside the Django auth.User form.
    Provides single-screen user management for human staff, AI agents, and clients.
    """
    model = Profile
    can_delete = False
    verbose_name = 'User Profile / AI Agent Settings'
    verbose_name_plural = 'User Profile / AI Agent Settings'
    fk_name = 'user'
    extra = 0
    form = ProfileAdminForm
    fieldsets = (
        ('Profile & Classification', {
            'fields': (
                ('user_type', 'is_agent'),
                'client',
                ('hermes_profile_name', 'display_name'),
                ('role', 'preferred_language'),
                'description',
            )
        }),
        ('AI Engine & Inference Configuration', {
            'description': 'Configure LLM inference, models, and reasoning budgets for this account.',
            'fields': (
                'provider',
                'model_name',
                'reasoning_effort',
                'is_active',
            )
        }),
        ('Advanced Credential & Endpoint Overrides', {
            'classes': ('collapse',),
            'description': (
                'Optional override: Leave blank to automatically inherit the global default credential '
                'for the selected provider. Select a credential only if this profile requires a dedicated '
                'API key, custom base_url (e.g. local Ollama/vLLM), or isolated tenant billing.'
            ),
            'fields': (
                'provider_credential',
            )
        }),
    )

    class Media:
        js = (
            '/static/admin/js/agent_profile_models.js?v=24.1',
            '/static/admin/js/hermes_profile_selector.js?v=24.1',
        )



# Unregister default UserAdmin and register enhanced CustomUserAdmin
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Enhanced UserAdmin with embedded ProfileInline and classification badges.
    """
    inlines = [ProfileInline]
    list_display = (
        'username',
        'email',
        'user_classification_badge',
        'hermes_profile_badge',
        'is_staff',
        'is_active',
    )
    list_filter = (
        'profile__is_agent',
        'profile__user_type',
        'is_staff',
        'is_superuser',
        'is_active',
    )

    def user_classification_badge(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile:
            return "—"
        if profile.is_agent:
            return format_html(
                '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">🤖 Agent</span>'
            )
        elif obj.is_staff or profile.user_type == 'human':
            return format_html(
                '<span style="background: #f1f5f9; color: #334155; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">👤 Staff</span>'
            )
        return format_html(
            '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">🌐 Client</span>'
        )
    user_classification_badge.short_description = 'User Type'

    def hermes_profile_badge(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile or not profile.hermes_profile_name:
            return "—"
        return format_html(
            '<code style="background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</code>',
            profile.hermes_profile_name
        )
    hermes_profile_badge.short_description = 'Hermes Engine Profile'

    class Media:
        js = (
            '/static/admin/js/agent_profile_models.js?v=24.1',
            '/static/admin/js/hermes_profile_selector.js?v=24.1',
        )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Direct administration of Profiles for bulk management or standalone configuration.
    """
    form = ProfileAdminForm
    list_display = (
        'display_name',
        'user_link',
        'user_type',
        'client',
        'is_agent',
        'hermes_profile_name',
        'role',
        'provider',
        'provider_credential',
        'model_name',
        'reasoning_effort',
        'is_active',
        'created_at',
    )
    list_filter = ('is_agent', 'user_type', 'client', 'role', 'reasoning_effort', 'provider', 'provider_credential', 'is_active')
    search_fields = ('name', 'hermes_profile_name', 'display_name', 'user__username', 'description')
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    fieldsets = (
        ('Profile & Identity', {
            'fields': (
                'user',
                ('user_type', 'is_agent'),
                'client',
                ('name', 'hermes_profile_name'),
                ('display_name', 'role'),
                'description',
            )
        }),
        ('LLM Inference & Model Selection', {
            'description': 'Configure the inference provider, foundation model, and thinking budget.',
            'fields': (
                'provider',
                'model_name',
                'reasoning_effort',
                'is_active',
            )
        }),
        ('Advanced Credential & Endpoint Overrides', {
            'classes': ('collapse',),
            'description': (
                'Optional override: Leave blank to automatically inherit the global default credential '
                'for the selected provider. Select a credential only if this profile requires a dedicated '
                'API key, custom base_url (e.g. local Ollama/vLLM), or isolated tenant billing.'
            ),
            'fields': (
                'provider_credential',
            )
        }),
        ('Metadata & Audit', {
            'classes': ('collapse',),
            'fields': (
                ('created_by', 'updated_by'),
                ('created_at', 'updated_at'),
            )
        }),
    )

    def user_link(self, obj):
        if not obj.user:
            return "—"
        url = f"/admin/auth/user/{obj.user.id}/change/"
        return format_html('<a href="{}" style="font-weight: 600;">{}</a>', url, obj.user.username)
    user_link.short_description = 'Linked User'

    class Media:
        js = (
            '/static/admin/js/agent_profile_models.js?v=24.1',
            '/static/admin/js/hermes_profile_selector.js?v=24.1',
        )


@admin.register(ProviderCredential)
class ProviderCredentialAdmin(admin.ModelAdmin):
    """
    Administration of encrypted LLM inference provider credentials.
    """
    form = ProviderCredentialAdminForm
    list_display = (
        'name',
        'provider_type_badge',
        'masked_key_display',
        'is_default',
        'is_active',
        'organization',
        'updated_at',
    )
    list_filter = ('provider_type', 'is_default', 'is_active', 'organization')
    search_fields = ('name', 'base_url')
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')
    actions = ['sync_to_hermes']

    def provider_type_badge(self, obj):
        colors = {
            'openrouter': '#0284c7',
            'gemini': '#059669',
            'openai': '#10b981',
            'anthropic': '#d97706',
            'groq': '#ea580c',
            'deepseek': '#4f46e5',
            'custom': '#64748b',
        }
        color = colors.get(obj.provider_type, '#64748b')
        return format_html(
            '<span style="background: {}18; color: {}; border: 1px solid {}33; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color, color, color, obj.get_provider_type_display()
        )
    provider_type_badge.short_description = 'Provider'

    def masked_key_display(self, obj):
        return format_html('<code style="font-family: monospace; font-size: 11px; background: #f8fafc; padding: 2px 6px; border-radius: 3px; border: 1px solid #e2e8f0;">{}</code>', obj.masked_key)
    masked_key_display.short_description = 'API Key (Masked)'

    def sync_to_hermes(self, request, queryset):
        from apps.integration.services.credential_sync import sync_hermes_runtime_credentials
        res = sync_hermes_runtime_credentials()
        self.message_user(request, f"Successfully synchronized {res.get('synced_keys_count', 0)} credentials across Hermes Agent runtime.")
    sync_to_hermes.short_description = "⚡ Synchronize active credentials to Hermes Agent runtime"


# Backward compatibility alias
AgentProfileAdmin = ProfileAdmin



@admin.register(HandshakeLog)
class HandshakeLogAdmin(admin.ModelAdmin):
    list_display = ('agent_id', 'version', 'status', 'client_ip', 'created_at')
    list_filter = ('status', 'agent_id', 'created_at')
    search_fields = ('agent_id', 'client_ip', 'payload')
    readonly_fields = ('id', 'agent_id', 'version', 'client_ip', 'payload', 'server_response', 'status', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False


@admin.register(SpendReport)
class SpendReportAdmin(admin.ModelAdmin):
    list_display = ('reported_by', 'created_by', 'total_cost_usd', 'daily_budget_usd', 'budget_status', 'total_tokens', 'total_api_calls', 'created_at')
    list_filter = ('budget_status', 'reported_by', 'created_at')
    search_fields = ('reported_by', 'payload')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'assigned_profile', 'created_by', 'status', 'review_verdict', 'reasoning_effort', 'cost_usd', 'created_at')
    list_filter = ('status', 'review_verdict', 'reasoning_effort', 'assigned_profile', 'created_at')
    search_fields = ('task_name', 'agent_name', 'reviewer_notes', 'input_payload', 'output_result')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')


@admin.register(ModelBenchmark)
class ModelBenchmarkAdmin(admin.ModelAdmin):
    list_display = (
        'model_identifier',
        'benchmark_name',
        'score_badge',
        'cost_display',
        'tokens_per_task',
        'agent_steps',
        'last_synced_at',
    )
    list_filter = ('benchmark_name', 'last_synced_at')
    search_fields = ('model_identifier', 'benchmark_name')
    readonly_fields = ('id', 'created_by', 'updated_by', 'created_at', 'updated_at', 'last_synced_at')
    actions = ['sync_benchmarks_now']

    def score_badge(self, obj):
        color = '#059669' if obj.score >= 70 else ('#d97706' if obj.score >= 60 else '#dc2626')
        return format_html(
            '<span style="background: {}18; color: {}; border: 1px solid {}44; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 12px;">{:.1f}%</span>',
            color, color, color, obj.score
        )
    score_badge.short_description = 'Benchmark Score'

    def cost_display(self, obj):
        if obj.avg_cost_per_task is not None:
            return f"${obj.avg_cost_per_task:.4f}"
        return "—"
    cost_display.short_description = 'Cost / Task'

    def sync_benchmarks_now(self, request, queryset):
        from apps.integration.services.benchmark_sync import sync_benchmarks
        res = sync_benchmarks()
        self.message_user(request, f"Successfully synchronized {res.get('synced_count', 0)} model benchmark records.")
    sync_benchmarks_now.short_description = "🔄 Synchronize frontier benchmarks from registry"


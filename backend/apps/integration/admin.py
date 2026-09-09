from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import HandshakeLog, Profile, SpendReport, AgentTask
from .forms import ProfileAdminForm


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
                ('hermes_profile_name', 'display_name'),
                ('role', 'preferred_language'),
                'description',
            )
        }),
        ('AI Engine & Inference Configuration', {
            'description': 'Configure LLM inference, models, and reasoning budgets for this account.',
            'fields': (
                ('provider', 'model_name'),
                'reasoning_effort',
                'is_active',
            )
        }),
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
            'admin/js/agent_profile_models.js',
            'admin/js/hermes_profile_selector.js',
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
        'is_agent',
        'hermes_profile_name',
        'role',
        'provider',
        'model_name',
        'reasoning_effort',
        'is_active',
        'created_at',
    )
    list_filter = ('is_agent', 'user_type', 'role', 'reasoning_effort', 'provider', 'is_active')
    search_fields = ('name', 'hermes_profile_name', 'display_name', 'user__username', 'description')
    readonly_fields = ('created_by', 'updated_by', 'created_at', 'updated_at')

    def user_link(self, obj):
        if not obj.user:
            return "—"
        url = f"/admin/auth/user/{obj.user.id}/change/"
        return format_html('<a href="{}" style="font-weight: 600;">{}</a>', url, obj.user.username)
    user_link.short_description = 'Linked User'

    class Media:
        js = (
            'admin/js/agent_profile_models.js',
            'admin/js/hermes_profile_selector.js',
        )


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

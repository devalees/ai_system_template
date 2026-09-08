from django.contrib import admin
from .models import HandshakeLog, AgentProfile, SpendReport, AgentTask
from .forms import AgentProfileAdminForm

@admin.register(HandshakeLog)
class HandshakeLogAdmin(admin.ModelAdmin):
    list_display = ('agent_id', 'version', 'status', 'client_ip', 'created_at')
    list_filter = ('status', 'agent_id', 'created_at')
    search_fields = ('agent_id', 'client_ip', 'payload')
    readonly_fields = ('id', 'agent_id', 'version', 'client_ip', 'payload', 'server_response', 'status', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    form = AgentProfileAdminForm
    fields = ('name', 'display_name', 'role', 'provider', 'model_name', 'is_active', 'description')
    list_display = ('display_name', 'name', 'role', 'provider', 'model_name', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'provider')
    search_fields = ('name', 'display_name', 'description')
    ordering = ('name',)

    class Media:
        js = ('admin/js/agent_profile_models.js',)


@admin.register(SpendReport)
class SpendReportAdmin(admin.ModelAdmin):
    list_display = ('reported_by', 'total_cost_usd', 'daily_budget_usd', 'budget_status', 'total_tokens', 'total_api_calls', 'created_at')
    list_filter = ('budget_status', 'reported_by', 'created_at')
    search_fields = ('reported_by', 'payload')
    readonly_fields = ('id', 'created_at')


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'assigned_profile', 'status', 'review_verdict', 'cost_usd', 'created_at')
    list_filter = ('status', 'review_verdict', 'assigned_profile', 'created_at')
    search_fields = ('task_name', 'agent_name', 'reviewer_notes', 'input_payload', 'output_result')
    readonly_fields = ('id', 'created_at', 'updated_at')

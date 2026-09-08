from django.contrib import admin
from .models import HandshakeLog, AgentTask

@admin.register(HandshakeLog)
class HandshakeLogAdmin(admin.ModelAdmin):
    list_display = ('agent_id', 'version', 'status', 'client_ip', 'created_at')
    list_filter = ('status', 'agent_id', 'created_at')
    search_fields = ('agent_id', 'client_ip', 'payload')
    readonly_fields = ('id', 'agent_id', 'version', 'client_ip', 'payload', 'server_response', 'status', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'agent_name', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'agent_name', 'created_at')
    search_fields = ('task_name', 'agent_name', 'input_payload', 'output_result')

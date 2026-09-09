"""
Django Admin Configuration for Centralized Automation Engine.
"""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AutomationRule, AutomationLog
from .forms import AutomationRuleAdminForm
from .tasks import execute_automation_rule_task

from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)

# Unregister raw Celery Beat plumbing models to keep admin clean and focused
for beat_model in (ClockedSchedule, CrontabSchedule, IntervalSchedule, SolarSchedule, PeriodicTask):
    try:
        admin.site.unregister(beat_model)
    except admin.sites.NotRegistered:
        pass


class AutomationLogInline(admin.TabularInline):
    """Inline view of recent execution logs inside the AutomationRule change form."""
    model = AutomationLog
    extra = 0
    can_delete = False
    max_num = 15
    fields = ('executed_at', 'status_badge', 'trigger_source', 'duration_display', 'error_snippet')
    readonly_fields = ('executed_at', 'status_badge', 'trigger_source', 'duration_display', 'error_snippet')
    ordering = ('-executed_at',)

    def has_add_permission(self, request, obj=None):
        return False

    def status_badge(self, obj):
        if obj.status == 'success':
            return format_html('<span style="background-color:#d1e7dd; color:#0f5132; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✓ SUCCESS</span>')
        elif obj.status == 'failed':
            return format_html('<span style="background-color:#f8d7da; color:#842029; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✗ FAILED</span>')
        return format_html('<span style="background-color:#cff4fc; color:#055160; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">⏳ {}</span>', obj.status.upper())
    status_badge.short_description = "Status"

    def duration_display(self, obj):
        return f"{obj.duration_ms} ms"
    duration_display.short_description = "Duration"

    def error_snippet(self, obj):
        if obj.error_message:
            return obj.error_message.splitlines()[0][:80]
        return "-"
    error_snippet.short_description = "Error Note"


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    """
    Control Plane for Automation Rules with quick toggles, Run Now dispatch,
    and embedded execution audit logs.
    """
    form = AutomationRuleAdminForm
    inlines = [AutomationLogInline]

    list_display = (
        'name',
        'trigger_badge',
        'execution_mode',
        'action_badge',
        'status_toggle',
        'run_count',
        'last_run_at',
        'run_now_action',
    )
    list_filter = ('trigger_type', 'action_category', 'is_active', 'execution_mode')
    search_fields = ('name', 'description', 'action_type', 'target_model')
    readonly_fields = ('run_count', 'last_run_at', 'next_run_at', 'created_at', 'updated_at')

    fieldsets = (
        ("Rule Identification", {
            "fields": ("name", "description", "is_active")
        }),
        ("Trigger Configuration", {
            "description": "Configure when this automation is triggered (Model Events, Scheduled Timers, or Webhooks).",
            "fields": (
                "trigger_type",
                "execution_mode",
                "target_model",
                "event_type",
                "filter_conditions",
            )
        }),
        ("Field Change & State Transition (Odoo-Style)", {
            "description": "Configure fine-grained triggers when a specific field value changes (e.g. status transition from 'review' to 'completed').",
            "fields": (
                "trigger_field",
                "previous_value",
                "target_value",
            ),
            "classes": ("collapse",)
        }),
        ("Time-Based Scheduling (Celery Beat)", {
            "description": "Configures periodic intervals or exact one-shot execution timestamps via Celery Beat.",
            "fields": (
                "schedule_unit",
                "schedule_value",
                "scheduled_time",
                "periodic_task",
            ),
            "classes": ("collapse",)
        }),
        ("Action Execution & Service Target", {
            "description": "Choose which service or agent to execute when triggered.",
            "fields": (
                "action_category",
                "action_type",
                "action_params",
            )
        }),
        ("Execution Metrics & State", {
            "fields": ("run_count", "last_run_at", "next_run_at", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    actions = ['activate_rules', 'pause_rules', 'trigger_rules_now']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:rule_id>/run-now/', self.admin_site.admin_view(self.run_now_view), name='automation_rule_run_now'),
        ]
        return custom_urls + urls

    def run_now_view(self, request, rule_id):
        """Allows executing a rule immediately on demand via Celery."""
        rule = self.get_object(request, rule_id)
        if not rule:
            messages.error(request, f"Automation Rule #{rule_id} not found.")
            return HttpResponseRedirect(reverse('admin:automation_automationrule_changelist'))

        # Dispatch via Celery worker
        async_res = execute_automation_rule_task.delay(rule.id, {"manual_trigger": True}, f"admin_run_now:{request.user.username}")
        messages.success(request, f"▶ Automation Action '{rule.name}' queued to Celery worker (Task ID: {async_res.id}).")
        return HttpResponseRedirect(reverse('admin:automation_automationrule_change', args=[rule.id]))

    def run_now_action(self, obj):
        url = reverse('admin:automation_rule_run_now', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color:#0d6efd; color:#ffffff; font-weight:bold; padding:3px 10px; border-radius:4px; text-decoration:none;">▶ Run Now</a>',
            url
        )
    run_now_action.short_description = "Execute"

    def status_toggle(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#198754; font-weight:bold;">🟢 Active</span>')
        return format_html('<span style="color:#6c757d; font-weight:bold;">⏸️ Paused</span>')
    status_toggle.short_description = "Status"

    def trigger_badge(self, obj):
        icons = {
            'model_event': '📦 Model Event',
            'time_based': f'⏱️ Every {obj.schedule_value} {obj.schedule_unit}',
            'webhook': '🌐 Webhook',
            'manual': '▶️ Manual',
        }
        label = icons.get(obj.trigger_type, obj.trigger_type)
        if obj.trigger_type == 'model_event' and obj.target_model:
            model_short = obj.target_model.split('.')[-1]
            if obj.trigger_field:
                trans = f" ➔ {obj.target_value}" if obj.target_value else ""
                label = f"📦 {model_short}.{obj.trigger_field}{trans}"
            else:
                label = f"📦 {model_short} ({obj.event_type})"
        return format_html('<code style="font-size:11px; padding:2px 6px; background:#f8f9fa; border:1px solid #dee2e6; border-radius:4px;">{}</code>', label)
    trigger_badge.short_description = "Trigger"

    def action_badge(self, obj):
        cat_badges = {
            'hermes_agent': ('🤖 Hermes', '#0dcaf0', '#000'),
            'internal_app': ('🐍 Django', '#198754', '#fff'),
            'script_service': ('📜 Script', '#6f42c1', '#fff'),
            'external_webhook': ('🌐 Webhook', '#fd7e14', '#fff'),
        }
        badge, bg, fg = cat_badges.get(obj.action_category, ('Action', '#6c757d', '#fff'))
        return format_html(
            '<span style="background-color:{}; color:{}; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:bold; margin-right:5px;">{}</span> <strong>{}</strong>',
            bg, fg, badge, obj.action_type
        )
    action_badge.short_description = "Action Target"

    @admin.action(description="🟢 Activate selected rules")
    def activate_rules(self, request, queryset):
        count = queryset.update(is_active=True)
        for rule in queryset:
            rule.save()
        messages.success(request, f"{count} rule(s) activated successfully.")

    @admin.action(description="⏸️ Pause selected rules")
    def pause_rules(self, request, queryset):
        count = queryset.update(is_active=False)
        for rule in queryset:
            rule.save()
        messages.success(request, f"{count} rule(s) paused.")

    @admin.action(description="▶ Dispatch selected rules now via Celery")
    def trigger_rules_now(self, request, queryset):
        count = 0
        for rule in queryset:
            execute_automation_rule_task.delay(rule.id, {"manual_trigger": True}, f"admin_bulk_trigger:{request.user.username}")
            count += 1
        messages.success(request, f"Dispatched {count} rule(s) to Celery workers.")


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    """Read-only audit log viewer for automated executions."""
    list_display = (
        'executed_at',
        'status_badge',
        'rule_link',
        'trigger_source',
        'duration_display',
    )
    list_filter = ('status', 'rule', 'executed_at')
    search_fields = ('trigger_source', 'error_message', 'rule__name')
    readonly_fields = [f.name for f in AutomationLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def rule_link(self, obj):
        if obj.rule:
            url = reverse('admin:automation_automationrule_change', args=[obj.rule.id])
            return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.rule.name)
        return "Ad-Hoc / Deleted Rule"
    rule_link.short_description = "Rule"

    def status_badge(self, obj):
        if obj.status == 'success':
            return format_html('<span style="background-color:#d1e7dd; color:#0f5132; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✓ SUCCESS</span>')
        elif obj.status == 'failed':
            return format_html('<span style="background-color:#f8d7da; color:#842029; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✗ FAILED</span>')
        return format_html('<span style="background-color:#cff4fc; color:#055160; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">⏳ {}</span>', obj.status.upper())
    status_badge.short_description = "Status"

    def duration_display(self, obj):
        return f"{obj.duration_ms} ms"
    duration_display.short_description = "Duration"

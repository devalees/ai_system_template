"""
Django Admin Configuration for Centralized Automation Engine.
"""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import AutomationTrigger, AutomationAction, AutomationLog, AutomationRule
from .forms import AutomationTriggerAdminForm, AutomationActionAdminForm
from .tasks import execute_automation_rule_task, execute_automation_action_task

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


def build_execution_context(model_identifier=None, user=None):
    """
    Builds a rich execution context for on-demand execution.
    If a model_identifier is provided (e.g. 'integration.AgentTask'), retrieves the latest record's
    fields or generates sensible default test values so prompt parameters & condition rules evaluate cleanly.
    """
    from django.apps import apps
    context = {
        "manual_trigger": True,
        "force_execution": True,
    }
    if user and hasattr(user, 'username'):
        context["username"] = user.username
        context["user_id"] = user.id

    if model_identifier:
        try:
            model_cls = apps.get_model(model_identifier)
            if model_cls:
                latest = model_cls.objects.order_by('-pk').first()
                if latest:
                    for field in latest._meta.fields:
                        val = getattr(latest, field.name, None)
                        if hasattr(val, 'pk'):
                            context[field.name] = val.pk
                        else:
                            context[field.name] = val
                    context['pk'] = latest.pk
                    context['id'] = latest.pk
                    context['model'] = model_identifier
        except Exception:
            pass

    # Fallback sensible defaults if not populated from a live record
    defaults = {
        "pk": context.get("pk", 1),
        "id": context.get("id", 1),
        "task_name": "Sample Agent Task",
        "cost_usd": 15.50,
        "status": "completed",
        "priority": "high",
        "description": "On-demand test execution triggered directly from Admin UI",
    }
    for k, v in defaults.items():
        context.setdefault(k, v)

    return context


class AutomationActionInline(admin.StackedInline):
    """
    Inline editor for sequenced AutomationActions inside the AutomationTrigger change form.
    Enables configuring 1-to-N action pipelines directly on the trigger event.
    """
    model = AutomationAction
    form = AutomationActionAdminForm
    extra = 1
    fk_name = 'trigger'
    fields = (
        ('name', 'sequence', 'is_active', 'run_inline_button'),
        'description',
        ('target_model', 'target_operation'),
        'field_mappings',
        ('action_category', 'action_type'),
        'action_params',
    )
    readonly_fields = ('run_inline_button',)
    ordering = ('sequence', 'created_at')

    def run_inline_button(self, obj):
        if obj and obj.pk:
            url = reverse('admin:automation_action_run_now', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color:#0d6efd; color:#ffffff; font-weight:bold; padding:4px 10px; border-radius:4px; text-decoration:none;">▶ Run Step #{}: {}</a>',
                url,
                obj.sequence,
                obj.name
            )
        return format_html('<span style="color:#6c757d; font-size:11px;">Save first to test</span>')
    run_inline_button.short_description = "Quick Run"


class AutomationLogInline(admin.TabularInline):
    """Inline view of recent execution logs inside the AutomationTrigger change form."""
    model = AutomationLog
    extra = 0
    fk_name = 'trigger'
    can_delete = False
    max_num = 15
    fields = ('executed_at', 'status_badge', 'action_display', 'trigger_source', 'duration_display', 'error_snippet')
    readonly_fields = ('executed_at', 'status_badge', 'action_display', 'trigger_source', 'duration_display', 'error_snippet')
    ordering = ('-executed_at',)

    def has_add_permission(self, request, obj=None):
        return False

    def action_display(self, obj):
        if obj.action:
            return f"[{obj.action.sequence}] {obj.action.name}"
        return "-"
    action_display.short_description = "Action"

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


@admin.register(AutomationTrigger)
class AutomationTriggerAdmin(admin.ModelAdmin):
    """
    Control Plane for Automation Triggers (WHEN events occur) with sequenced Action pipelines.
    """
    form = AutomationTriggerAdminForm
    inlines = [AutomationActionInline, AutomationLogInline]

    class Media:
        js = (
            'automation/js/automation_reactive_admin.js',
        )

    list_display = (
        'name',
        'scope_badge',
        'trigger_badge',
        'execution_mode',
        'actions_summary',
        'status_toggle',
        'trigger_count',
        'last_triggered_at',
        'run_now_action',
    )
    list_filter = ('is_system', 'trigger_type', 'is_active', 'execution_mode')
    search_fields = ('name', 'description', 'trigger_model')
    readonly_fields = ('trigger_count', 'last_triggered_at', 'created_by', 'updated_by', 'created_at', 'updated_at')

    fieldsets = (
        ("Trigger Event Identification", {
            "fields": ("name", "description", "is_active", "is_system")
        }),
        ("Trigger Configuration (Source Event)", {
            "description": "Configure when this automation is triggered (Model Events, Scheduled Timers, or Webhooks).",
            "fields": (
                "trigger_type",
                "execution_mode",
                "trigger_model",
                "event_type",
                "filter_conditions",
                "condition_rules",
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
        ("Execution Metrics & Audit", {
            "fields": ("trigger_count", "last_triggered_at", ("created_by", "updated_by"), ("created_at", "updated_at")),
            "classes": ("collapse",)
        }),
    )

    actions = ['activate_triggers', 'pause_triggers', 'trigger_now']

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        system_triggers = queryset.filter(is_system=True)
        if system_triggers.exists():
            names = ", ".join(system_triggers.values_list('name', flat=True))
            messages.warning(
                request,
                f"Protected system automation triggers cannot be deleted: {names}."
            )
        non_system = queryset.filter(is_system=False)
        for trigger in non_system:
            trigger.delete()
        if non_system.exists():
            messages.success(request, f"Successfully deleted {non_system.count()} custom automation trigger(s).")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:trigger_id>/run-now/', self.admin_site.admin_view(self.run_now_view), name='automation_trigger_run_now'),
        ]
        return custom_urls + urls

    def run_now_view(self, request, trigger_id):
        """Allows executing all actions for a trigger immediately on demand via Celery."""
        trigger = self.get_object(request, trigger_id)
        if not trigger:
            messages.error(request, f"Automation Trigger #{trigger_id} not found.")
            return HttpResponseRedirect(reverse('admin:automation_automationtrigger_changelist'))

        context = build_execution_context(trigger.trigger_model, user=request.user)
        # Dispatch via Celery worker
        async_res = execute_automation_rule_task.delay(trigger.id, context, f"admin_run_now:{request.user.username}")
        messages.success(request, f"▶ Automation Pipeline '{trigger.name}' queued to Celery worker (Task ID: {async_res.id}).")
        return HttpResponseRedirect(reverse('admin:automation_automationtrigger_change', args=[trigger.id]))

    def run_now_action(self, obj):
        url = reverse('admin:automation_trigger_run_now', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color:#0d6efd; color:#ffffff; font-weight:bold; padding:3px 10px; border-radius:4px; text-decoration:none;">▶ Run Pipeline</a>',
            url
        )
    run_now_action.short_description = "Execute"

    def scope_badge(self, obj):
        if obj.is_system:
            return format_html('<span style="background-color:#ffe69c; color:#664d03; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">🛡️ SYSTEM</span>')
        return format_html('<span style="color:#6c757d; font-size:11px; padding:3px 8px;">User Defined</span>')
    scope_badge.short_description = "Scope"

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
        if obj.trigger_type == 'model_event' and obj.trigger_model:
            model_short = obj.trigger_model.split('.')[-1]
            if obj.trigger_field:
                trans = f" ➔ {obj.target_value}" if obj.target_value else ""
                label = f"📦 {model_short}.{obj.trigger_field}{trans}"
            else:
                label = f"📦 {model_short} ({obj.event_type})"
        return format_html('<code style="font-size:11px; padding:2px 6px; background:#f8f9fa; border:1px solid #dee2e6; border-radius:4px;">{}</code>', label)
    trigger_badge.short_description = "Trigger"

    def actions_summary(self, obj):
        actions = list(obj.actions.filter(is_active=True).order_by('sequence'))
        if not actions:
            return format_html('<em>No Actions</em>')
        badges = []
        for act in actions:
            badges.append(f'<span style="background-color:#0d6efd; color:#fff; padding:2px 6px; border-radius:8px; font-size:10px; margin-right:3px;">#{act.sequence} {act.name}</span>')
        return format_html(" ".join(badges))
    actions_summary.short_description = "Actions Pipeline"

    @admin.action(description="🟢 Activate selected triggers")
    def activate_triggers(self, request, queryset):
        count = queryset.update(is_active=True)
        for trigger in queryset:
            trigger.save()
        messages.success(request, f"{count} trigger(s) activated successfully.")

    @admin.action(description="⏸️ Pause selected triggers")
    def pause_triggers(self, request, queryset):
        count = queryset.update(is_active=False)
        for trigger in queryset:
            trigger.save()
        messages.success(request, f"{count} trigger(s) paused.")

    @admin.action(description="▶ Dispatch selected pipelines now via Celery")
    def trigger_now(self, request, queryset):
        count = 0
        for trigger in queryset:
            execute_automation_rule_task.delay(trigger.id, {"manual_trigger": True}, f"admin_bulk_trigger:{request.user.username}")
            count += 1
        messages.success(request, f"Dispatched {count} pipeline(s) to Celery workers.")


# Alias for backward compatibility
AutomationRuleAdmin = AutomationTriggerAdmin


@admin.register(AutomationAction)
class AutomationActionAdmin(admin.ModelAdmin):
    """
    Dedicated view for inspecting and managing individual Automation Actions.
    """
    form = AutomationActionAdminForm

    class Media:
        js = (
            'automation/js/automation_reactive_admin.js',
        )
    list_display = (
        'name',
        'trigger_link',
        'sequence',
        'target_badge',
        'is_active',
        'is_system',
        'run_count',
        'last_run_at',
        'run_now_action',
    )
    list_filter = ('is_system', 'is_active', 'action_category', 'target_operation')
    search_fields = ('name', 'description', 'target_model', 'action_type')
    readonly_fields = ('run_count', 'last_run_at', 'created_at', 'updated_at')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:action_id>/run-now/', self.admin_site.admin_view(self.run_action_now_view), name='automation_action_run_now'),
        ]
        return custom_urls + urls

    def run_action_now_view(self, request, action_id):
        """Allows executing a single action immediately on demand via Celery."""
        action = self.get_object(request, action_id)
        if not action:
            messages.error(request, f"Automation Action #{action_id} not found.")
            return HttpResponseRedirect(reverse('admin:automation_automationaction_changelist'))

        model_name = (action.trigger.trigger_model if action.trigger else None) or action.target_model
        context = build_execution_context(model_name, user=request.user)

        async_res = execute_automation_action_task.delay(
            action.id,
            context,
            f"admin_run_action_now:{request.user.username}"
        )
        messages.success(
            request,
            f"▶ Automation Action '{action.name}' (Step #{action.sequence}) queued to Celery worker (Task ID: {async_res.id})."
        )
        return HttpResponseRedirect(reverse('admin:automation_automationaction_change', args=[action.id]))

    def run_now_action(self, obj):
        url = reverse('admin:automation_action_run_now', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color:#0d6efd; color:#ffffff; font-weight:bold; padding:3px 10px; border-radius:4px; text-decoration:none;">▶ Run Action</a>',
            url
        )
    run_now_action.short_description = "Execute"

    def trigger_link(self, obj):
        url = reverse('admin:automation_automationtrigger_change', args=[obj.trigger.id])
        return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.trigger.name)
    trigger_link.short_description = "Trigger"

    def target_badge(self, obj):
        cat_badges = {
            'hermes_agent': ('🤖 Hermes', '#0dcaf0', '#000'),
            'internal_app': ('🐍 Django', '#198754', '#fff'),
            'script_service': ('📜 Script', '#6f42c1', '#fff'),
            'external_webhook': ('🌐 Webhook', '#fd7e14', '#fff'),
        }
        badges = []
        if obj.target_model and obj.target_operation:
            target_short = obj.target_model.split('.')[-1]
            op_label = f"{obj.target_operation.upper()} {target_short}"
            badges.append(f'<span style="background-color:#20c997; color:#fff; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:bold; margin-right:4px;">📦 {op_label}</span>')

        if obj.action_type and obj.action_type not in ('', 'none', 'target_crud'):
            badge, bg, fg = cat_badges.get(obj.action_category, ('Action', '#6c757d', '#fff'))
            badges.append(f'<span style="background-color:{bg}; color:{fg}; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:bold; margin-right:4px;">{badge}</span> <strong>{obj.action_type}</strong>')

        return format_html(" ".join(badges) if badges else "<em>None</em>")
    target_badge.short_description = "Action Target"


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    """Read-only audit log viewer for automated executions."""
    list_display = (
        'executed_at',
        'status_badge',
        'trigger_link',
        'action_display',
        'trigger_source',
        'duration_display',
    )
    list_filter = ('status', 'executed_at')
    search_fields = ('trigger_source', 'error_message', 'trigger__name', 'action__name')
    readonly_fields = [f.name for f in AutomationLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def trigger_link(self, obj):
        if obj.trigger:
            url = reverse('admin:automation_automationtrigger_change', args=[obj.trigger.id])
            return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.trigger.name)
        elif obj.rule:
            url = reverse('admin:automation_automationtrigger_change', args=[obj.rule.id])
            return format_html('<a href="{}"><strong>{}</strong></a>', url, obj.rule.name)
        return "Ad-Hoc / Deleted"
    trigger_link.short_description = "Trigger"

    def action_display(self, obj):
        if obj.action:
            url = reverse('admin:automation_automationaction_change', args=[obj.action.id])
            return format_html('<a href="{}">#{} {}</a>', url, obj.action.sequence, obj.action.name)
        return "-"
    action_display.short_description = "Action"

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

"""
Read-Only Django Admin Interface for Comprehensive Activity Audit Trail.

Provides an enterprise-grade compliance inspector with visual diff cards,
action badge indicators, and immutable access controls.
"""

import json
from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from apps.audit.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Strictly read-only administrative viewer for audit log entries.
    """
    list_display = (
        "timestamp",
        "actor_display",
        "actor_type",
        "action_badge",
        "target_display",
        "status_badge",
        "organization",
        "ip_address",
        "request_id",
    )
    list_filter = (
        "action",
        "actor_type",
        "status",
        "organization",
    )
    search_fields = (
        "object_repr",
        "object_id",
        "actor__username",
        "actor__email",
        "ip_address",
        "request_id",
    )
    ordering = ("-timestamp",)

    readonly_fields = (
        "id",
        "timestamp",
        "organization",
        "actor",
        "actor_type",
        "action",
        "status",
        "content_type",
        "object_id",
        "object_repr",
        "changes_diff_card",
        "ip_address",
        "user_agent",
        "request_id",
        "metadata_display",
    )

    fieldsets = (
        (_("Event Overview"), {
            "fields": ("id", "timestamp", "action", "status")
        }),
        (_("Actor & Telemetry"), {
            "fields": ("actor", "actor_type", "organization", "ip_address", "user_agent", "request_id")
        }),
        (_("Target Entity"), {
            "fields": ("content_type", "object_id", "object_repr")
        }),
        (_("Attribute Differences"), {
            "fields": ("changes_diff_card",)
        }),
        (_("Context Metadata"), {
            "fields": ("metadata_display",),
            "classes": ("collapse",)
        }),
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description=_("Actor"))
    def actor_display(self, obj: ActivityLog) -> str:
        if obj.actor:
            return obj.actor.username
        return obj.get_actor_type_display()

    @admin.display(description=_("Target"))
    def target_display(self, obj: ActivityLog) -> str:
        if obj.object_repr:
            return obj.object_repr
        if obj.content_type and obj.object_id:
            return f"{obj.content_type.model} #{obj.object_id}"
        return "-"

    @admin.display(description=_("Action"))
    def action_badge(self, obj: ActivityLog):
        color_map = {
            ActivityLog.ACTION_CREATE: ("#10b981", "#ffffff"),       # Emerald
            ActivityLog.ACTION_UPDATE: ("#3b82f6", "#ffffff"),       # Blue
            ActivityLog.ACTION_DELETE: ("#f59e0b", "#ffffff"),       # Amber
            ActivityLog.ACTION_RESTORE: ("#06b6d4", "#ffffff"),      # Cyan
            ActivityLog.ACTION_HARD_DELETE: ("#ef4444", "#ffffff"),  # Red
            ActivityLog.ACTION_LOGIN: ("#8b5cf6", "#ffffff"),        # Purple
            ActivityLog.ACTION_LOGOUT: ("#6b7280", "#ffffff"),       # Gray
            ActivityLog.ACTION_LOGIN_FAILED: ("#dc2626", "#ffffff"), # Crimson
            ActivityLog.ACTION_EXPORT: ("#0284c7", "#ffffff"),       # Sky
            ActivityLog.ACTION_CUSTOM: ("#64748b", "#ffffff"),       # Slate
        }
        bg, fg = color_map.get(obj.action, ("#6b7280", "#ffffff"))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; text-transform: uppercase;">{}</span>',
            bg, fg, obj.get_action_display()
        )

    @admin.display(description=_("Status"))
    def status_badge(self, obj: ActivityLog):
        status_map = {
            ActivityLog.STATUS_SUCCESS: ("#dcfce7", "#166534"),
            ActivityLog.STATUS_FAILURE: ("#fee2e2", "#991b1b"),
            ActivityLog.STATUS_WARNING: ("#fef3c7", "#92400e"),
        }
        bg, fg = status_map.get(obj.status, ("#f3f4f6", "#374151"))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 7px; border-radius: 4px; font-weight: 500; font-size: 11px;">{}</span>',
            bg, fg, obj.get_status_display()
        )

    @admin.display(description=_("Attribute Changes Diff"))
    def changes_diff_card(self, obj: ActivityLog):
        if not obj.changes:
            return mark_safe('<em style="color: #9ca3af;">No attribute changes recorded for this event.</em>')

        rows_html = []
        for field, diff in sorted(obj.changes.items()):
            old_val = escape(json.dumps(diff.get("old"), default=str) if diff.get("old") is not None else "-")
            new_val = escape(json.dumps(diff.get("new"), default=str) if diff.get("new") is not None else "-")

            row = f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 6px 12px; font-family: monospace; font-weight: 600; color: #1e293b;">{escape(field)}</td>
                <td style="padding: 6px 12px; font-family: monospace; background-color: #fee2e2; color: #991b1b; text-decoration: line-through;">{old_val}</td>
                <td style="padding: 6px 12px; font-family: monospace; background-color: #dcfce7; color: #166534; font-weight: 600;">{new_val}</td>
            </tr>
            """
            rows_html.append(row)

        table_html = f"""
        <table style="width: 100%; max-width: 900px; border-collapse: collapse; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; font-size: 12px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; text-align: left;">
                    <th style="padding: 8px 12px; font-weight: 600; color: #475569;">Field</th>
                    <th style="padding: 8px 12px; font-weight: 600; color: #475569;">Prior Value (Old)</th>
                    <th style="padding: 8px 12px; font-weight: 600; color: #475569;">Updated Value (New)</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
        """
        return mark_safe(table_html)

    @admin.display(description=_("Context Metadata"))
    def metadata_display(self, obj: ActivityLog):
        if not obj.metadata:
            return mark_safe('<em style="color: #9ca3af;">No extra metadata attached.</em>')
        pretty_json = escape(json.dumps(obj.metadata, indent=2, default=str))
        return mark_safe(f'<pre style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; font-size: 12px;">{pretty_json}</pre>')

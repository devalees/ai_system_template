"""
Django Admin interface for Universal Notifications Engine.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin view for Notification records with colored level badges and read action."""

    list_display = [
        "title",
        "recipient",
        "level_badge",
        "channel",
        "is_read",
        "organization",
        "created_at",
    ]
    list_filter = ["level", "channel", "is_read", "created_at", "organization"]
    search_fields = ["title", "message", "recipient__username", "actor__username"]
    readonly_fields = ["id", "created_at", "updated_at", "read_at"]
    actions = ["mark_selected_as_read"]

    def level_badge(self, obj: Notification) -> str:
        """Render colored HTML badge for notification level."""
        colors = {
            Notification.LEVEL_INFO: "#2196F3",
            Notification.LEVEL_SUCCESS: "#4CAF50",
            Notification.LEVEL_WARNING: "#FF9800",
            Notification.LEVEL_ERROR: "#F44336",
        }
        icons = {
            Notification.LEVEL_INFO: "ℹ️",
            Notification.LEVEL_SUCCESS: "✅",
            Notification.LEVEL_WARNING: "⚠️",
            Notification.LEVEL_ERROR: "🚨",
        }
        color = colors.get(obj.level, "#9E9E9E")
        icon = icons.get(obj.level, "🔔")
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">{} {}</span>',
            color,
            icon,
            obj.get_level_display(),
        )

    level_badge.short_description = _("Level")

    @admin.action(description=_("Mark selected notifications as read"))
    def mark_selected_as_read(self, request, queryset):
        """Bulk admin action to mark notifications as read."""
        updated = 0
        for n in queryset.filter(is_read=False):
            n.mark_as_read()
            updated += 1
        self.message_user(request, f"Successfully marked {updated} notification(s) as read.")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin view for NotificationPreference multi-channel configurations."""

    list_display = [
        "user",
        "in_app_enabled",
        "email_enabled",
        "webhook_enabled",
        "slack_enabled",
        "updated_at",
    ]
    list_filter = ["in_app_enabled", "email_enabled", "webhook_enabled", "slack_enabled"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]

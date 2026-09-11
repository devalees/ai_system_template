"""
Django Admin interface for Client Management.

Provides:
- ClientAdmin: First-class administration of external Client accounts,
  embedding multi-tenant scoping, 1-to-many user inlines, AI service toggles,
  visual spend progress bars, and document attachments.
- ClientUserInline: Tabular view of user accounts linked to this client.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.clients.models import Client
from apps.integration.models import Profile
from apps.media.admin import ClientDocumentInline


class ClientUserInline(admin.TabularInline):
    """
    Inline listing of User Profiles belonging to this Client.
    Allows administrators to assign, view, or manage client users directly.
    """
    model = Profile
    fk_name = "client"
    extra = 0
    can_delete = False
    fields = ["user", "display_name", "user_type", "is_active", "created_at"]
    readonly_fields = ["created_at"]
    verbose_name = _("Linked User Account")
    verbose_name_plural = _("Linked User Accounts")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Dedicated administration portal for external business clients.
    """
    list_display = [
        "name",
        "organization",
        "primary_contact_name",
        "primary_contact_email",
        "is_ai_enabled_badge",
        "ai_budget_display",
        "ai_spend_display",
        "spend_progress_gauge",
        "budget_status_badge",
        "linked_users_badge",
        "status_badge",
        "created_at",
    ]
    list_filter = [
        "organization",
        "status",
        "is_ai_enabled",
        "created_at",
    ]
    search_fields = [
        "name",
        "slug",
        "primary_contact_name",
        "primary_contact_email",
        "organization__name",
    ]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = [
        "spend_progress_gauge",
        "budget_status_badge",
        "linked_users_badge",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    inlines = [ClientUserInline, ClientDocumentInline]

    fieldsets = (
        (_("Client & Organization Identity"), {
            "fields": (
                ("organization", "status"),
                ("name", "slug"),
            )
        }),
        (_("Primary Contact Information"), {
            "fields": (
                ("primary_contact_name", "primary_contact_email"),
                "primary_contact_phone",
            )
        }),
        (_("AI Service & Dollar Budget Governance"), {
            "description": _(
                "Configure AI concierge access, dollar expenditure ceilings, and inspect live consumption milestones. "
                "Clients interact exclusively with the Client Service & Communications Coordinator (comms_agent)."
            ),
            "fields": (
                "is_ai_enabled",
                ("ai_budget_usd", "ai_spend_usd"),
                ("spend_progress_gauge", "budget_status_badge"),
            )
        }),
        (_("Administrative Notes"), {
            "fields": ("notes",)
        }),
        (_("Metadata & Audit"), {
            "classes": ("collapse",),
            "fields": (
                ("created_by", "updated_by"),
                ("created_at", "updated_at"),
            )
        }),
    )

    def is_ai_enabled_badge(self, obj: Client) -> str:
        """Visual green/gray toggle badge for AI service authorization."""
        if obj.is_ai_enabled:
            return format_html(
                '<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">'
                '🤖 AI Active</span>'
            )
        return format_html(
            '<span style="background: #f1f5f9; color: #64748b; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">'
            '⛔ Disabled</span>'
        )
    is_ai_enabled_badge.short_description = _("AI Entitlement")

    def ai_budget_display(self, obj: Client) -> str:
        """Formatted dollar budget ceiling."""
        return f"${float(obj.ai_budget_usd):.2f}"
    ai_budget_display.short_description = _("Budget")

    def ai_spend_display(self, obj: Client) -> str:
        """Formatted dollar spend."""
        return f"${float(obj.ai_spend_usd):.4f}"
    ai_spend_display.short_description = _("Spend")

    def spend_progress_gauge(self, obj: Client) -> str:
        """Dynamic color-coded CSS visual progress bar."""
        pct = min(obj.ai_budget_percentage, 100.0)
        raw_pct = obj.ai_budget_percentage

        # Color palette depending on percentage milestone
        if raw_pct >= 100.0:
            bar_color = "#ef4444"  # Red
            bg_color = "#fee2e2"
            text_color = "#991b1b"
        elif raw_pct >= 75.0:
            bar_color = "#f97316"  # Orange
            bg_color = "#ffedd5"
            text_color = "#9a3412"
        elif raw_pct >= 50.0:
            bar_color = "#eab308"  # Yellow
            bg_color = "#fef9c3"
            text_color = "#854d0e"
        else:
            bar_color = "#10b981"  # Emerald Green
            bg_color = "#d1fae5"
            text_color = "#065f46"

        return format_html(
            '<div style="min-width: 140px; display: inline-block;">'
            '  <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">'
            '    <span style="font-weight: 600; color: {};">{:.1f}%</span>'
            '    <span style="color: #64748b;">${:.2f} / ${:.2f}</span>'
            '  </div>'
            '  <div style="background: #e2e8f0; border-radius: 9999px; height: 6px; width: 100%; overflow: hidden;">'
            '    <div style="background: {}; height: 100%; width: {}%; border-radius: 9999px; transition: width 0.3s ease;"></div>'
            '  </div>'
            '</div>',
            text_color,
            raw_pct,
            float(obj.ai_spend_usd),
            float(obj.ai_budget_usd),
            bar_color,
            pct,
        )
    spend_progress_gauge.short_description = _("Spend Gauge")

    def budget_status_badge(self, obj: Client) -> str:
        """Milestone status pill badge."""
        status = obj.ai_budget_status
        if status == "disabled":
            return format_html('<span style="background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">Disabled</span>')
        elif status == "exceeded":
            return format_html('<span style="background: #fee2e2; color: #b91c1c; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">🚨 Exceeded (100%)</span>')
        elif status == "warning":
            return format_html('<span style="background: #ffedd5; color: #c2410c; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">⚠️ Warning (75%)</span>')
        elif status == "velocity_check":
            return format_html('<span style="background: #fef9c3; color: #a16207; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">📊 Velocity (50%)</span>')
        return format_html('<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">✓ Healthy</span>')
    budget_status_badge.short_description = _("Milestone")

    def status_badge(self, obj: Client) -> str:
        """Render client account status badge."""
        if obj.status == Client.STATUS_ACTIVE:
            return format_html('<span style="background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">Active</span>')
        elif obj.status == Client.STATUS_SUSPENDED:
            return format_html('<span style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">Suspended</span>')
        return format_html('<span style="background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">Inactive</span>')
    status_badge.short_description = _("Status")

    def linked_users_badge(self, obj: Client) -> str:
        """Render linked user count badge."""
        count = obj.linked_users_count
        return format_html(
            '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">👥 {} users</span>',
            count
        )
    linked_users_badge.short_description = _("Users")

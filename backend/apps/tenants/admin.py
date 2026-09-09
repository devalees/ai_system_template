"""
Django Admin interfaces for Multi-Tenancy and Workspaces.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.tenants.models import Organization, OrganizationMembership, OrganizationInvitation


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    fields = ("user", "role", "is_active", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "tier_badge",
        "seats_display",
        "domain",
        "is_active",
        "created_at",
    )
    list_filter = ("tier", "is_active", "created_at")
    search_fields = ("name", "slug", "domain")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by")
    inlines = [OrganizationMembershipInline]

    fieldsets = (
        (_("Workspace Information"), {
            "fields": ("name", "slug", "domain", "is_active")
        }),
        (_("Subscription & Limits"), {
            "fields": ("tier", "max_users")
        }),
        (_("Configuration"), {
            "fields": ("metadata",),
            "classes": ("collapse",)
        }),
        (_("Audit Metadata"), {
            "fields": ("id", "created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def tier_badge(self, obj):
        colors = {
            Organization.TIER_FREE: "#64748b",
            Organization.TIER_STARTER: "#0284c7",
            Organization.TIER_PRO: "#6366f1",
            Organization.TIER_ENTERPRISE: "#10b981",
        }
        color = colors.get(obj.tier, "#64748b")
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 9px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>',
            color,
            obj.get_tier_display().upper()
        )
    tier_badge.short_description = _("Tier")

    def seats_display(self, obj):
        used = obj.active_members_count
        max_seats = obj.max_users
        return f"{used} / {max_seats}"
    seats_display.short_description = _("Active Seats")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role_badge", "is_active", "created_at")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__username", "user__email", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by")
    autocomplete_fields = ("user", "organization")

    def role_badge(self, obj):
        colors = {
            OrganizationMembership.ROLE_OWNER: "#ef4444",
            OrganizationMembership.ROLE_ADMIN: "#f59e0b",
            OrganizationMembership.ROLE_MEMBER: "#3b82f6",
            OrganizationMembership.ROLE_VIEWER: "#6b7280",
            OrganizationMembership.ROLE_GUEST: "#9ca3af",
        }
        color = colors.get(obj.role, "#6b7280")
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; border-radius:3px; font-size:11px; font-weight:600;">{}</span>',
            color,
            obj.get_role_display()
        )
    role_badge.short_description = _("Role")


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
        "role",
        "status_badge",
        "expires_at",
        "invited_by",
        "created_at",
    )
    list_filter = ("status", "role", "organization")
    search_fields = ("email", "organization__name", "token")
    readonly_fields = ("id", "token", "accepted_at", "created_at", "updated_at")
    actions = ["revoke_invitations"]

    def status_badge(self, obj):
        colors = {
            OrganizationInvitation.STATUS_PENDING: "#f59e0b",
            OrganizationInvitation.STATUS_ACCEPTED: "#10b981",
            OrganizationInvitation.STATUS_EXPIRED: "#6b7280",
            OrganizationInvitation.STATUS_REVOKED: "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; border-radius:3px; font-size:11px; font-weight:600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _("Status")

    def revoke_invitations(self, request, queryset):
        revoked_count = 0
        for invite in queryset:
            if invite.status == OrganizationInvitation.STATUS_PENDING:
                invite.revoke()
                revoked_count += 1
        self.message_user(request, _(f"Successfully revoked {revoked_count} invitation(s)."))
    revoke_invitations.short_description = _("Revoke selected invitations")

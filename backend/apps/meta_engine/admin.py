"""
Django Admin Configuration for Metadata Engine.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    SystemModule,
    MetaModel,
    MetaField,
    MetaAction,
    MetaView,
    MetaMenu,
    MetaRule,
    MetaReport,
)


class MetaFieldInline(admin.TabularInline):
    """
    Inline field editor inside MetaModel form for defining attributes in-place.
    """
    model = MetaField
    extra = 1
    fk_name = "model"
    fields = (
        "sequence",
        "name",
        "label",
        "field_type",
        "required",
        "unique",
        "index",
        "default_value",
        "fk_target_model",
    )
    ordering = ("sequence", "name")


class MetaViewInline(admin.TabularInline):
    """
    Inline view layouts attached directly to MetaModel.
    """
    model = MetaView
    extra = 0
    fk_name = "model"
    fields = ("name", "view_type", "is_default", "is_active")


class MetaReportInline(admin.TabularInline):
    """
    Inline printable reports attached directly to MetaModel.
    """
    model = MetaReport
    extra = 0
    fk_name = "model"
    fields = ("name", "slug", "report_type", "paper_format", "is_default", "is_active")


@admin.register(MetaModel)
class MetaModelAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "name",
        "app_label",
        "table_name",
        "fields_count_badge",
        "is_system",
        "is_auditable",
        "is_active",
        "created_at",
    )
    list_filter = ("is_system", "is_auditable", "is_soft_delete", "is_active", "app_label")
    search_fields = ("name", "label", "table_name", "description")
    inlines = [MetaFieldInline, MetaViewInline, MetaReportInline]
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")

    fieldsets = (
        (_("Model Identification"), {
            "fields": (
                ("label", "label_plural"),
                ("name", "app_label"),
                "table_name",
                "description",
            )
        }),
        (_("Runtime Capabilities & Behaviors"), {
            "fields": (
                ("is_system", "is_auditable", "is_soft_delete", "is_active"),
                "ordering_field",
            )
        }),
        (_("Audit Log"), {
            "fields": (("created_by", "updated_by"), ("created_at", "updated_at")),
            "classes": ("collapse",),
        }),
    )

    def fields_count_badge(self, obj):
        count = obj.fields.count()
        return format_html(
            '<span style="background: #e0f2fe; color: #0284c7; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{} fields</span>',
            count
        )
    fields_count_badge.short_description = _("Fields")


@admin.register(MetaField)
class MetaFieldAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "name",
        "model",
        "type_badge",
        "required",
        "unique",
        "index",
        "sequence",
    )
    list_filter = ("field_type", "required", "unique", "index", "model__app_label")
    search_fields = ("name", "label", "model__name")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")

    fieldsets = (
        (_("Field Identity"), {
            "fields": (
                "model",
                ("label", "name"),
                ("field_type", "sequence"),
                "help_text",
            )
        }),
        (_("Constraints & Validation"), {
            "fields": (
                ("required", "unique", "index"),
                ("max_length", "max_digits", "decimal_places"),
                "default_value",
                "choices",
            )
        }),
        (_("Relational Link Configuration"), {
            "fields": (
                ("fk_target_model", "fk_target_app_model"),
                "on_delete_behavior",
            ),
            "classes": ("collapse",),
        }),
        (_("Audit Log"), {
            "fields": (("created_by", "updated_by"), ("created_at", "updated_at")),
            "classes": ("collapse",),
        }),
    )

    def type_badge(self, obj):
        return format_html(
            '<span style="background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 11px;">{}</span>',
            obj.get_field_type_display()
        )
    type_badge.short_description = _("Type")


@admin.register(MetaView)
class MetaViewAdmin(admin.ModelAdmin):
    list_display = ("name", "model", "view_type", "is_default", "is_active", "created_at")
    list_filter = ("view_type", "is_default", "is_active", "model__app_label")
    search_fields = ("name", "model__name")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")


@admin.register(MetaAction)
class MetaActionAdmin(admin.ModelAdmin):
    list_display = ("name", "action_type", "target_model", "is_active", "created_at")
    list_filter = ("action_type", "is_active")
    search_fields = ("name", "target_model__name", "server_handler")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")


@admin.register(MetaMenu)
class MetaMenuAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "app_label", "sequence", "action", "is_active")
    list_filter = ("app_label", "is_active")
    search_fields = ("name", "app_label")
    ordering = ("sequence", "name")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")


@admin.register(MetaRule)
class MetaRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "model",
        "group",
        "perm_read",
        "perm_write",
        "perm_create",
        "perm_delete",
        "is_active",
    )
    list_filter = ("is_active", "group", "model__app_label")
    search_fields = ("name", "model__name")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")


@admin.register(MetaReport)
class MetaReportAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "model",
        "report_type",
        "paper_format",
        "orientation",
        "is_default",
        "is_active",
    )
    list_filter = ("report_type", "paper_format", "orientation", "is_default", "is_active")
    search_fields = ("name", "slug", "model__name")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at")


@admin.register(SystemModule)
class SystemModuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "app_id",
        "version",
        "category",
        "status_badge",
        "author",
        "installed_at",
    )
    list_filter = ("status", "category")
    search_fields = ("name", "app_id", "description", "author")
    readonly_fields = ("id", "created_by", "updated_by", "created_at", "updated_at", "installed_at")

    def status_badge(self, obj):
        colors = {
            "installed": "#10b981",
            "uninstalled": "#6b7280",
            "to_upgrade": "#f59e0b",
            "error": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 0.75rem;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _("Status")


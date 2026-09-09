"""
Administrative Interface for Dynamic Visual Reporting & PDF Generation Engine.
"""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.reports.models import ReportExecutionLog, ReportTemplate


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "target_model_badge",
        "page_format_badge",
        "orientation_badge",
        "is_default",
        "is_active",
        "actions_column",
    ]
    list_filter = ["page_format", "orientation", "is_default", "is_active", "target_model"]
    search_fields = ["name", "slug", "target_model", "description", "compiled_html"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (_("General Information"), {
            "fields": ("organization", "name", "slug", "description", "target_model", "is_default", "is_active")
        }),
        (_("Page & Layout Configuration"), {
            "fields": ("page_format", "orientation", "layout_schema")
        }),
        (_("HTML & CSS Template Editor"), {
            "fields": ("compiled_html", "css_styles", "header_html", "footer_html")
        }),
    )

    def target_model_badge(self, obj: ReportTemplate) -> str:
        return format_html(
            '<span style="background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-weight: 500; font-family: monospace;">{}</span>',
            obj.target_model
        )
    target_model_badge.short_description = _("Target Model")

    def page_format_badge(self, obj: ReportTemplate) -> str:
        return format_html(
            '<span style="background: #f1f5f9; color: #334155; padding: 3px 6px; border-radius: 4px;">{}</span>',
            obj.get_page_format_display()
        )
    page_format_badge.short_description = _("Format")

    def orientation_badge(self, obj: ReportTemplate) -> str:
        icon = "📄" if obj.orientation == "portrait" else "📜"
        return format_html("{} {}", icon, obj.get_orientation_display())
    orientation_badge.short_description = _("Orientation")

    def actions_column(self, obj: ReportTemplate) -> str:
        preview_url = reverse("admin:reports_reporttemplate_preview", args=[obj.pk])
        render_url = reverse("admin:reports_reporttemplate_render", args=[obj.pk])
        return format_html(
            '<a class="button" style="padding: 2px 8px; font-size: 11px; background: #0284c7; color: #fff; margin-right: 4px;" href="{}" target="_blank">▶ Preview HTML</a>'
            '<a class="button" style="padding: 2px 8px; font-size: 11px; background: #059669; color: #fff;" href="{}" target="_blank">▶ Render PDF</a>',
            preview_url,
            render_url
        )
    actions_column.short_description = _("Actions")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/preview/",
                self.admin_site.admin_view(self.admin_preview_view),
                name="reports_reporttemplate_preview",
            ),
            path(
                "<path:object_id>/render/",
                self.admin_site.admin_view(self.admin_render_view),
                name="reports_reporttemplate_render",
            ),
        ]
        return custom_urls + urls

    def admin_preview_view(self, request, object_id):
        template_obj = self.get_object(request, object_id)
        if not template_obj:
            messages.error(request, _("Report template not found."))
            return redirect("admin:reports_reporttemplate_changelist")

        from apps.reports.engine import ReportEngine
        from django.http import HttpResponse
        html = ReportEngine.render_html(template_obj)
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    def admin_render_view(self, request, object_id):
        template_obj = self.get_object(request, object_id)
        if not template_obj:
            messages.error(request, _("Report template not found."))
            return redirect("admin:reports_reporttemplate_changelist")

        from apps.reports.engine import ReportEngine
        from django.http import HttpResponse
        pdf_bytes, _, _, error_msg = ReportEngine.render_pdf(template_obj)

        if error_msg and not pdf_bytes:
            messages.error(request, f"PDF Render Error: {error_msg}")
            return redirect("admin:reports_reporttemplate_change", object_id)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{template_obj.slug}.pdf"'
        return response


@admin.register(ReportExecutionLog)
class ReportExecutionLogAdmin(admin.ModelAdmin):
    list_display = [
        "template",
        "format_badge",
        "record_id",
        "duration_ms_formatted",
        "file_size_human",
        "status_badge",
        "actor",
        "created_at",
    ]
    list_filter = ["format", "status", "created_at"]
    search_fields = ["record_id", "error_message", "template__name", "template__slug"]
    readonly_fields = [
        "organization",
        "template",
        "format",
        "record_id",
        "duration_ms",
        "file_size_bytes",
        "status",
        "error_message",
        "document",
        "actor",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def format_badge(self, obj: ReportExecutionLog) -> str:
        color = "#0369a1" if obj.format == "pdf" else "#047857"
        return format_html(
            '<span style="background: #e0f2fe; color: {}; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.format.upper()
        )
    format_badge.short_description = _("Format")

    def status_badge(self, obj: ReportExecutionLog) -> str:
        color = "#16a34a" if obj.status == "success" else "#dc2626"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _("Status")

    def duration_ms_formatted(self, obj: ReportExecutionLog) -> str:
        return f"{obj.duration_ms} ms"
    duration_ms_formatted.short_description = _("Duration")

    def file_size_human(self, obj: ReportExecutionLog) -> str:
        from apps.media.models import format_human_size
        return format_human_size(obj.file_size_bytes)
    file_size_human.short_description = _("Size")

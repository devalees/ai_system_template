"""
Data Models for Dynamic Visual Reporting & PDF Generation Engine.

Provides:
- ReportTemplate: Multi-tenant, soft-deletable document template specification
  supporting Jinja2/Django HTML compilation, visual layout schemas, and CSS @page rules.
- ReportExecutionLog: Audit log tracking template rendering duration, format (HTML/PDF),
  requesting actor, output file size, and generated media attachments.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel
from apps.tenants.base_models import TenantAwareModel


class PageFormatChoices(models.TextChoices):
    A4 = "A4", _("A4 Standard (210 x 297 mm)")
    LETTER = "Letter", _("US Letter (8.5 x 11 in)")
    LEGAL = "Legal", _("US Legal (8.5 x 14 in)")
    THERMAL_80MM = "thermal_80mm", _("Thermal Receipt (80mm Roll)")


class PageOrientationChoices(models.TextChoices):
    PORTRAIT = "portrait", _("Portrait")
    LANDSCAPE = "landscape", _("Landscape")


class ReportExecutionFormatChoices(models.TextChoices):
    HTML = "html", _("HTML Preview")
    PDF = "pdf", _("Vector PDF Document")


class ReportExecutionStatusChoices(models.TextChoices):
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")


class ReportTemplate(TenantAwareModel, SoftDeleteModel):
    """
    Dynamic Report Template specification supporting HTML/CSS templates,
    CSS @page paged media rules, and introspection token placeholders.
    """
    name = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Template Name"),
        help_text=_("Human-readable name of the report template.")
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name=_("Template Slug"),
        help_text=_("Unique identifier slug used for API and automation execution.")
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Description"),
        help_text=_("Detailed documentation on report contents and usage.")
    )
    target_model = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Target Model"),
        help_text=_("Model identifier e.g. 'auth.User', 'integration.AgentTask', 'crm.lead'.")
    )
    page_format = models.CharField(
        max_length=32,
        choices=PageFormatChoices.choices,
        default=PageFormatChoices.A4,
        verbose_name=_("Page Format"),
        help_text=_("Paper size specification.")
    )
    orientation = models.CharField(
        max_length=16,
        choices=PageOrientationChoices.choices,
        default=PageOrientationChoices.PORTRAIT,
        verbose_name=_("Orientation"),
        help_text=_("Page layout orientation (Portrait or Landscape).")
    )
    layout_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Layout Schema"),
        help_text=_("JSON visual coordinate tree for visual drag-and-drop report builders.")
    )
    compiled_html = models.TextField(
        blank=True,
        default="",
        verbose_name=_("HTML Template"),
        help_text=_("Jinja2 / Django HTML template markup with variable placeholders.")
    )
    css_styles = models.TextField(
        blank=True,
        default="",
        verbose_name=_("CSS Stylesheet"),
        help_text=_("Custom CSS rules applied during PDF generation (including @page media rules).")
    )
    header_html = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Header HTML"),
        help_text=_("Running page header HTML content.")
    )
    footer_html = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Footer HTML"),
        help_text=_("Running page footer HTML content with page counters.")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Is Default"),
        help_text=_("Default report template for the specified target model.")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this template is available for rendering.")
    )

    class Meta:
        verbose_name = _("Report Template")
        verbose_name_plural = _("Report Templates")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "target_model", "is_active"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.target_model}] ({self.get_page_format_display()})"


class ReportExecutionLog(TenantAwareModel):
    """
    Audit log tracking report generation requests, rendering metrics,
    execution errors, and generated media document attachments.
    """
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_logs",
        verbose_name=_("Report Template")
    )
    format = models.CharField(
        max_length=16,
        choices=ReportExecutionFormatChoices.choices,
        default=ReportExecutionFormatChoices.PDF,
        verbose_name=_("Output Format")
    )
    record_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Record ID"),
        help_text=_("Primary key of target model record evaluated in this report run.")
    )
    duration_ms = models.IntegerField(
        default=0,
        verbose_name=_("Duration (ms)"),
        help_text=_("Execution time in milliseconds.")
    )
    file_size_bytes = models.IntegerField(
        default=0,
        verbose_name=_("File Size (Bytes)")
    )
    status = models.CharField(
        max_length=16,
        choices=ReportExecutionStatusChoices.choices,
        default=ReportExecutionStatusChoices.SUCCESS,
        verbose_name=_("Status")
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message")
    )
    document = models.ForeignKey(
        "media.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_execution_logs",
        verbose_name=_("Generated Document")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Requesting Actor")
    )

    class Meta:
        verbose_name = _("Report Execution Log")
        verbose_name_plural = _("Report Execution Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["template", "status"]),
        ]

    def __str__(self) -> str:
        template_name = self.template.name if self.template else "Deleted Template"
        return f"{template_name} ({self.format.upper()}) - {self.status} [{self.duration_ms}ms]"

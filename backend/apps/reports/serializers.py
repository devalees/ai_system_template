"""
DRF Serializers for Dynamic Visual Reporting & PDF Generation Engine.
"""

from rest_framework import serializers

from apps.reports.models import ReportExecutionLog, ReportTemplate


class ReportTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ReportTemplate specifications and layouts."""

    page_format_display = serializers.CharField(source="get_page_format_display", read_only=True)
    orientation_display = serializers.CharField(source="get_orientation_display", read_only=True)

    class Meta:
        model = ReportTemplate
        fields = [
            "id",
            "organization",
            "name",
            "slug",
            "description",
            "target_model",
            "page_format",
            "page_format_display",
            "orientation",
            "orientation_display",
            "layout_schema",
            "compiled_html",
            "css_styles",
            "header_html",
            "footer_html",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]


class ReportExecutionLogSerializer(serializers.ModelSerializer):
    """Serializer for ReportExecutionLog audit records."""

    template_name = serializers.ReadOnlyField(source="template.name", default=None)
    actor_username = serializers.ReadOnlyField(source="actor.username", default=None)
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportExecutionLog
        fields = [
            "id",
            "organization",
            "template",
            "template_name",
            "format",
            "record_id",
            "duration_ms",
            "file_size_bytes",
            "status",
            "error_message",
            "document",
            "document_url",
            "actor",
            "actor_username",
            "created_at",
        ]
        read_only_fields = fields

    def get_document_url(self, obj: ReportExecutionLog) -> str:
        """Construct download endpoint URL for generated report document if attached."""
        if obj.document_id:
            return f"/api/v1/media/documents/{obj.document_id}/download/"
        return ""


class ModelTokenSerializer(serializers.Serializer):
    """Serializer for template designer variable tokens."""

    token = serializers.CharField()
    label = serializers.CharField()
    type = serializers.CharField()
    help_text = serializers.CharField(required=False, allow_blank=True)

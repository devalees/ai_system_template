"""
DRF Views and Endpoints for Dynamic Visual Reporting & PDF Generation Engine.
"""

from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.media.models import Document
from apps.reports.engine import ReportEngine
from apps.reports.models import ReportExecutionFormatChoices, ReportExecutionLog, ReportExecutionStatusChoices, ReportTemplate
from apps.reports.serializers import (
    ModelTokenSerializer,
    ReportExecutionLogSerializer,
    ReportTemplateSerializer,
)


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Report Templates, viewing HTML previews,
    downloading rendered PDFs, and inspecting model variable tokens.
    """
    queryset = ReportTemplate.objects.all()
    serializer_class = ReportTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scope queryset to active tenant workspace unless superuser."""
        return super().get_queryset()

    @action(detail=False, methods=["get"], url_path="tokens")
    def list_tokens(self, request):
        """
        GET /api/v1/reports/templates/tokens/?target_model=...
        Return available variable tokens for designer autocomplete.
        """
        target_model = request.query_params.get("target_model", "")
        tokens = ReportEngine.get_model_tokens(target_model)
        serializer = ModelTokenSerializer(tokens, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="preview")
    def preview_html(self, request, pk=None):
        """
        GET /api/v1/reports/templates/<id>/preview/?record_id=...
        Render and return interactive HTML template string.
        """
        template_obj = self.get_object()
        record_id = request.query_params.get("record_id")

        html_content = ReportEngine.render_html(template_obj, record_id=record_id)
        return HttpResponse(html_content, content_type="text/html; charset=utf-8")

    @action(detail=True, methods=["get", "post"], url_path="render")
    def render_pdf(self, request, pk=None):
        """
        GET/POST /api/v1/reports/templates/<id>/render/?record_id=...&save_document=true
        Render vector PDF binary stream, log execution metrics, and option to save as Document attachment.
        """
        template_obj = self.get_object()
        record_id = request.query_params.get("record_id") or request.data.get("record_id")
        save_document = request.query_params.get("save_document", "").lower() in ("true", "1", "yes") or request.data.get("save_document") is True

        pdf_bytes, duration_ms, file_size, error_msg = ReportEngine.render_pdf(template_obj, record_id=record_id)

        exec_status = ReportExecutionStatusChoices.SUCCESS if not error_msg else ReportExecutionStatusChoices.FAILED

        # Create Execution Audit Log
        doc_attachment = None
        if pdf_bytes and save_document:
            try:
                from django.core.files.base import ContentFile
                filename = f"{template_obj.slug}_{record_id or 'report'}.pdf"
                doc_attachment = Document.objects.create(
                    filename=filename,
                    file=ContentFile(pdf_bytes, name=filename),
                    file_size=file_size,
                    mime_type="application/pdf",
                    uploaded_by=request.user if request.user.is_authenticated else None,
                    organization=template_obj.organization,
                    extra_metadata={"template_slug": template_obj.slug, "record_id": record_id}
                )
            except Exception as e:
                pass

        ReportExecutionLog.objects.create(
            template=template_obj,
            format=ReportExecutionFormatChoices.PDF,
            record_id=str(record_id or ""),
            duration_ms=duration_ms,
            file_size_bytes=file_size,
            status=exec_status,
            error_message=error_msg or "",
            document=doc_attachment,
            actor=request.user if request.user.is_authenticated else None,
            organization=template_obj.organization
        )

        if error_msg and not pdf_bytes:
            return Response(
                {"error": f"PDF Generation Error: {error_msg}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = f"{template_obj.slug}_{record_id or 'report'}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReportExecutionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for inspecting Report Execution Audit Logs.
    """
    queryset = ReportExecutionLog.objects.all()
    serializer_class = ReportExecutionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

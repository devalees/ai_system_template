"""
Automation Action Registry Integration for Dynamic Visual Reporting Engine.
"""

import logging
from typing import Any, Dict

from apps.automation.registry import register_action
from apps.reports.engine import ReportEngine
from apps.reports.models import ReportExecutionFormatChoices, ReportExecutionLog, ReportExecutionStatusChoices, ReportTemplate

logger = logging.getLogger(__name__)


def generate_pdf_report_action(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Action Handler: Compiles a vector PDF report from template and record ID,
    attaches it to media storage as a Document, and dispatches audit log.
    """
    action_params = context.get("action_params", {})
    template_identifier = action_params.get("template_slug") or action_params.get("template_id") or action_params.get("template")
    record_id = action_params.get("record_id") or context.get("pk") or context.get("record_id") or context.get("id")

    if not template_identifier:
        return {
            "status": "failed",
            "error": "Missing required parameter 'template_slug' in action_params."
        }

    # Resolve ReportTemplate
    template_obj = (
        ReportTemplate.objects.filter(slug=template_identifier).first()
        or ReportTemplate.objects.filter(pk=template_identifier if str(template_identifier).isdigit() else None).first()
    )

    if not template_obj:
        return {
            "status": "failed",
            "error": f"Report template '{template_identifier}' not found."
        }

    # Render PDF
    pdf_bytes, duration_ms, file_size, error_msg = ReportEngine.render_pdf(
        template_obj,
        record_id=str(record_id or ""),
        extra_context=context
    )

    if error_msg or not pdf_bytes:
        return {
            "status": "failed",
            "error": error_msg or "Empty PDF payload generated."
        }

    # Save to media Documents
    doc_attachment = None
    try:
        from django.core.files.base import ContentFile
        from apps.media.models import Document

        filename = f"{template_obj.slug}_{record_id or 'report'}.pdf"
        doc_attachment = Document.objects.create(
            filename=filename,
            file=ContentFile(pdf_bytes, name=filename),
            file_size=file_size,
            mime_type="application/pdf",
            organization=template_obj.organization,
            extra_metadata={"template_slug": template_obj.slug, "record_id": record_id}
        )
    except Exception as e:
        logger.warning(f"Failed to create Document attachment for generated report: {e}")

    # Log Execution
    exec_log = ReportExecutionLog.objects.create(
        template=template_obj,
        format=ReportExecutionFormatChoices.PDF,
        record_id=str(record_id or ""),
        duration_ms=duration_ms,
        file_size_bytes=file_size,
        status=ReportExecutionStatusChoices.SUCCESS,
        document=doc_attachment,
        organization=template_obj.organization
    )

    return {
        "status": "success",
        "report_log_id": str(exec_log.id),
        "document_id": str(doc_attachment.id) if doc_attachment else None,
        "file_size": file_size,
        "duration_ms": duration_ms,
    }


def register_report_actions():
    """Register report engine actions with central ServiceRegistry."""
    register_action(
        name="generate_pdf_report",
        category="internal_app",
        description="Generates a vector PDF report from a ReportTemplate and attaches it as a Document.",
        presets=[
            {
                "name": "📄 Auto-Generate Task Completion PDF Report",
                "description": "Compiles task summary PDF report upon task approval/completion.",
                "params": {
                    "template_slug": "task_completion_report",
                    "record_id": "{{pk}}",
                    "save_document": True
                }
            }
        ]
    )(generate_pdf_report_action)

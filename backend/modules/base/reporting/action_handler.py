"""Action handler integrating Report Generation into the Event-Driven Automated Actions (TCA) subsystem."""

import uuid
import logging
from typing import Optional, Dict, Any
from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.reporting.service import ReportService
from modules.base.mail_gateway.service import MailService

logger = logging.getLogger("sovereign.reporting.action_handler")


class GenerateReportActionConfig(BaseModel):
    """Configuration schema for Generate Report automated action."""
    report_code: str = Field(..., description="Standard or dynamic report code (e.g. 'documents.storage_audit', 'identity.user_directory')")
    format: str = Field(default="pdf", description="Output format: 'pdf', 'xlsx', or 'csv'")
    template_id: Optional[uuid.UUID] = Field(None, description="Optional styling template UUID override")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Report query parameters (supports Jinja2 variables like '{{record.id}}')")
    attach_to_record: bool = Field(default=True, description="Attach generated document to the trigger record")
    send_email: bool = Field(default=False, description="Dispatch generated document as email attachment")
    recipient_email: Optional[str] = Field(None, description="Recipient email address (supports '{{record.email}}')")


class GenerateReportActionHandler(BaseActionHandler):
    """Action handler that executes reports, generates documents, and attaches them to records."""

    action_type = "generate_report"
    title = "Generate Headless Report & Document"
    description = "Execute a standard or dynamic report, render document (PDF, Excel, CSV), attach to record, and optionally dispatch via email."
    config_schema = GenerateReportActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: GenerateReportActionConfig,
    ) -> Dict[str, Any]:
        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
        }

        # 1. Resolve template variables in parameters
        resolved_params: Dict[str, Any] = {}
        for k, v in config.parameters.items():
            if isinstance(v, str) and "{{" in v:
                v = Template(v).render(**template_vars)
            resolved_params[k] = v

        # 2. Render and attach report document
        res_model = context.target_model if config.attach_to_record else None
        res_id = context.target_id if config.attach_to_record else None

        attachment_result = await ReportService.export_and_attach(
            db=db,
            company_id=context.company_id,
            user_id=context.user_id,
            report_code=config.report_code,
            output_format=config.format,
            params=resolved_params,
            template_id=config.template_id,
            res_model=res_model,
            res_id=res_id,
        )

        # 3. Optional Email Dispatch
        email_dispatched = False
        if config.send_email and config.recipient_email:
            to_email = config.recipient_email
            if "{{" in to_email:
                to_email = Template(to_email).render(**template_vars)

            if to_email and "@" in to_email:
                try:
                    await MailService.enqueue_mail(
                        db=db,
                        company_id=context.company_id,
                        to_email=to_email,
                        subject=f"Automated Document: {attachment_result.get('file_name', 'Report')}",
                        body_html=f"<p>Please find attached the generated report document <b>{attachment_result.get('file_name')}</b>.</p>",
                        res_model=context.target_model,
                        res_id=context.target_id,
                    )
                    email_dispatched = True
                except Exception as mail_exc:
                    logger.error(f"Failed to enqueue report email to {to_email}: {mail_exc}")

        return {
            "status": "generated",
            "report_code": config.report_code,
            "format": config.format,
            "attachment": attachment_result,
            "email_dispatched": email_dispatched,
        }


# Automatically register into action registry
action_registry.register(GenerateReportActionHandler())

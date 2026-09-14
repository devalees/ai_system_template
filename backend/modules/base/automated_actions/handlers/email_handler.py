"""Action handler for dispatching transactional emails via Mail Gateway."""

import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext
from modules.base.mail_gateway.service import MailService
from modules.base.mail_gateway.models import MailTemplate


class SendEmailActionConfig(BaseModel):
    """Configuration schema for Send Email action."""
    template_code: Optional[str] = Field(None, description="Unique code of the MailTemplate to render and send")
    template_id: Optional[uuid.UUID] = Field(None, description="UUID of the MailTemplate to use")
    recipient_field: str = Field("email", description="Field on trigger record containing recipient email (e.g. 'email', 'partner_email')")
    static_recipient: Optional[str] = Field(None, description="Static recipient email address if not dynamically extracted from record")
    subject_override: Optional[str] = Field(None, description="Optional subject line override")


class SendEmailActionHandler(BaseActionHandler):
    """Action handler that renders and enqueues an outbound email."""

    action_type = "send_email"
    title = "Send Email"
    description = "Dispatch dynamic transactional email using the Mail Gateway and Jinja2 templates."
    config_schema = SendEmailActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: SendEmailActionConfig,
    ) -> Dict[str, Any]:
        # 1. Resolve recipient email
        recipient = config.static_recipient
        if not recipient and config.recipient_field:
            recipient = context.record_data.get(config.recipient_field)
            if not recipient and hasattr(context.record, config.recipient_field):
                recipient = getattr(context.record, config.recipient_field)

        if not recipient:
            return {"status": "skipped", "reason": f"Recipient email not found in field '{config.recipient_field}'"}

        # 2. Resolve template ID
        template_id = config.template_id
        if not template_id and config.template_code:
            stmt = select(MailTemplate).where(
                MailTemplate.company_id == context.company_id,
                MailTemplate.code == config.template_code,
            )
            template = (await db.execute(stmt)).scalar_one_or_none()
            if template:
                template_id = template.id

        # 3. Compile template context from record
        template_vars = {
            "record": context.record_data,
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
            **context.extra_context,
        }

        # 4. Enqueue email via MailService
        queue_entry = await MailService.enqueue_mail(
            db=db,
            company_id=context.company_id,
            recipients=[str(recipient)],
            template_id=template_id,
            subject=config.subject_override,
            template_context=template_vars,
            res_model=context.target_model,
            res_id=context.target_id,
        )

        return {
            "status": "enqueued",
            "queue_id": str(queue_entry.id),
            "recipient": str(recipient),
            "template_id": str(template_id) if template_id else None,
        }

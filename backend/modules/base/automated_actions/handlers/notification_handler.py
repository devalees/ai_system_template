"""Action handler for multi-channel notifications (in-app, webpush, push)."""

import uuid
from typing import Optional, Dict, Any, List
from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext
from modules.base.notification_engine.service import NotificationService
from modules.base.notification_engine.schemas import SendNotificationRequest


class SendNotificationActionConfig(BaseModel):
    """Configuration schema for Send Notification action."""
    title_template: str = Field(..., description="Jinja2 template for notification title")
    body_template: str = Field(..., description="Jinja2 template for notification body")
    recipient_user_id_field: str = Field("created_by_id", description="Field on trigger record holding recipient User UUID")
    static_recipient_id: Optional[uuid.UUID] = Field(None, description="Static target user UUID if not dynamically extracted")
    channels: List[str] = Field(default_factory=lambda: ["in_app"], description="List of delivery channels ('in_app', 'webpush')")
    notification_type: str = Field("alert", description="Category: 'system' | 'message' | 'task' | 'alert'")
    priority: str = Field("normal", description="Priority: 'low' | 'normal' | 'high' | 'urgent'")
    action_url: Optional[str] = Field(None, description="Optional relative URL to open when notification is clicked")


class SendNotificationActionHandler(BaseActionHandler):
    """Action handler that delivers multi-channel notifications to users."""

    action_type = "send_notification"
    title = "Send Multi-Channel Notification"
    description = "Deliver in-app, WebPush, or push notification to target user."
    config_schema = SendNotificationActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: SendNotificationActionConfig,
    ) -> Dict[str, Any]:
        # 1. Resolve recipient user ID
        recipient_id = config.static_recipient_id
        if not recipient_id and config.recipient_user_id_field:
            val = context.record_data.get(config.recipient_user_id_field)
            if not val and hasattr(context.record, config.recipient_user_id_field):
                val = getattr(context.record, config.recipient_user_id_field)
            if val:
                recipient_id = uuid.UUID(str(val)) if isinstance(val, (str, uuid.UUID)) else None

        if not recipient_id:
            return {"status": "skipped", "reason": f"Recipient user ID not found in field '{config.recipient_user_id_field}'"}

        # 2. Render templates with context variables
        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
        }
        title = Template(config.title_template).render(**template_vars)
        body = Template(config.body_template).render(**template_vars)
        action_url = Template(config.action_url).render(**template_vars) if config.action_url else None

        # 3. Dispatch via NotificationService
        req = SendNotificationRequest(
            recipient_id=recipient_id,
            title=title,
            body=body,
            channels=config.channels,
            notification_type=config.notification_type,
            priority=config.priority,
            action_url=action_url,
            res_model=context.target_model,
            res_id=context.target_id,
        )

        resp = await NotificationService.send_notification(
            db=db,
            req=req,
            company_id=context.company_id,
            sender_id=context.user_id,
        )

        return {
            "status": "sent",
            "notification_id": str(resp.notification_id) if resp.notification_id else None,
            "recipient_id": str(recipient_id),
            "dispatched_channels": resp.dispatched_channels,
        }

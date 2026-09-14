"""Action handler for posting automated notes and activity logs to record chatter threads."""

import uuid
from typing import Optional, Dict, Any
from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.handlers.base import BaseActionHandler, ActionContext
from modules.base.chatter.service import ChatterService


class PostChatterActionConfig(BaseModel):
    """Configuration schema for Post Chatter action."""
    body_template: str = Field(..., description="Jinja2 template for the chatter message body")
    message_type: str = Field("comment", description="Type: 'comment' | 'notification' | 'activity'")
    author_type: str = Field("system", description="Author identifier: 'system' | 'ai_agent'")


class PostChatterActionHandler(BaseActionHandler):
    """Action handler that creates a polymorphic chatter message on the target record."""

    action_type = "post_chatter"
    title = "Post to Chatter Thread"
    description = "Post an automated note, audit message, or AI finding into the record's chatter timeline."
    config_schema = PostChatterActionConfig

    async def execute(
        self,
        db: AsyncSession,
        context: ActionContext,
        config: PostChatterActionConfig,
    ) -> Dict[str, Any]:
        template_vars = {
            "record": context.record_data,
            "diff": context.diff or {},
            "company_id": str(context.company_id),
            "target_model": context.target_model,
            "target_id": str(context.target_id),
        }
        body = Template(config.body_template).render(**template_vars)

        message = await ChatterService.post_message(
            db=db,
            res_model=context.target_model,
            res_id=context.target_id,
            body=body,
            company_id=context.company_id,
            author_id=context.user_id,
            author_type=config.author_type,
            message_type=config.message_type,
            metadata_info={"automated_action": True, "trigger_type": context.trigger_type},
        )

        return {
            "status": "posted",
            "message_id": str(message.id),
            "res_model": context.target_model,
            "res_id": str(context.target_id),
        }

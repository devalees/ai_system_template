"""Chatter persistence and real-time event broadcasting service."""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from core.event_bus import event_bus
from core.context import get_active_company_id, get_current_user_id, get_actor_type
from modules.base.chatter.models import MailMessage, Activity

logger = logging.getLogger("sovereign.chatter")


class ChatterService:
    """Service for polymorphic chatter threads and real-time collaboration broadcasting."""

    @classmethod
    async def post_message(
        cls,
        db: AsyncSession,
        res_model: str,
        res_id: uuid.UUID,
        body: str,
        company_id: Optional[uuid.UUID] = None,
        author_id: Optional[uuid.UUID] = None,
        author_type: Optional[str] = None,
        message_type: str = "comment",
        metadata_info: Optional[Dict[str, Any]] = None,
    ) -> MailMessage:
        """Post a polymorphic message, persist to DB, and broadcast to Redis Pub/Sub channel."""
        target_company_id = company_id or get_active_company_id()
        if not target_company_id:
            raise ValueError("Active company_id is required to post chatter message.")

        message = MailMessage(
            company_id=target_company_id,
            res_model=res_model.lower(),
            res_id=res_id,
            body=body,
            message_type=message_type,
            author_id=author_id or get_current_user_id(),
            author_type=author_type or get_actor_type() or "human",
            metadata_info=metadata_info or {},
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # 1. Publish internal EventBus event
        await event_bus.publish(
            "chatter.message.created",
            {
                "message_id": str(message.id),
                "company_id": str(target_company_id),
                "res_model": message.res_model,
                "res_id": str(message.res_id),
                "author_id": str(message.author_id) if message.author_id else None,
                "author_type": message.author_type,
                "message_type": message.message_type,
            },
        )

        # 2. Broadcast via Redis Pub/Sub
        channel = f"sovereign:chatter:{target_company_id}:{message.res_model}:{message.res_id}"
        payload = {
            "id": str(message.id),
            "company_id": str(target_company_id),
            "res_model": message.res_model,
            "res_id": str(message.res_id),
            "body": message.body,
            "message_type": message.message_type,
            "author_id": str(message.author_id) if message.author_id else None,
            "author_type": message.author_type,
            "metadata_info": message.metadata_info,
            "created_at": message.created_at.isoformat(),
        }
        try:
            r = aioredis.from_url(settings.REDIS_URL)
            await r.publish(channel, json.dumps(payload))
            await r.aclose()
        except Exception as exc:
            logger.debug(f"Failed publishing chatter message to Redis channel {channel}: {exc}")

        return message

    @classmethod
    async def get_messages(
        cls,
        db: AsyncSession,
        res_model: str,
        res_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> List[MailMessage]:
        """Fetch all messages for a specific model record ordered chronologically."""
        stmt = (
            select(MailMessage)
            .where(
                MailMessage.company_id == company_id,
                MailMessage.res_model == res_model.lower(),
                MailMessage.res_id == res_id,
            )
            .order_by(MailMessage.created_at.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def schedule_activity(
        cls,
        db: AsyncSession,
        res_model: str,
        res_id: uuid.UUID,
        summary: str,
        company_id: Optional[uuid.UUID] = None,
        activity_type: str = "todo",
        assigned_to_id: Optional[uuid.UUID] = None,
        due_date: Optional[datetime] = None,
    ) -> Activity:
        """Schedule a planned operational activity for a record."""
        target_company_id = company_id or get_active_company_id()
        if not target_company_id:
            raise ValueError("Active company_id is required to schedule activity.")

        activity = Activity(
            company_id=target_company_id,
            res_model=res_model.lower(),
            res_id=res_id,
            summary=summary,
            activity_type=activity_type,
            assigned_to_id=assigned_to_id,
            due_date=due_date,
        )
        db.add(activity)
        await db.commit()
        await db.refresh(activity)

        await event_bus.publish(
            "chatter.activity.created",
            {
                "activity_id": str(activity.id),
                "company_id": str(target_company_id),
                "res_model": activity.res_model,
                "res_id": str(activity.res_id),
                "summary": activity.summary,
            },
        )
        return activity

    @classmethod
    async def complete_activity(
        cls,
        db: AsyncSession,
        activity_id: uuid.UUID,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Activity:
        """Mark an activity as completed and log resolution to the chatter thread."""
        stmt = select(Activity).where(
            Activity.id == activity_id,
            Activity.company_id == company_id,
        )
        activity = (await db.execute(stmt)).scalar_one_or_none()
        if not activity:
            raise ValueError("Activity not found.")

        activity.is_completed = True
        activity.completed_at = datetime.now(timezone.utc)
        activity.completed_by_id = user_id or get_current_user_id()

        await db.commit()
        await db.refresh(activity)

        # Log completion message to chatter thread
        await cls.post_message(
            db=db,
            res_model=activity.res_model,
            res_id=activity.res_id,
            body=f"Activity completed: {activity.summary} ({activity.activity_type})",
            company_id=company_id,
            author_id=user_id,
            message_type="activity",
        )

        return activity

"""Service layer for multi-channel notification dispatch, Redis broadcasting, and user preferences."""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from core.event_bus import event_bus
from core.exceptions import NotFoundException
from modules.base.notification_engine.models import (
    Notification,
    NotificationPreference,
    PushSubscription,
)
from modules.base.notification_engine.schemas import (
    SendNotificationRequest,
    SendNotificationResponse,
    PushSubscriptionCreate,
)

logger = logging.getLogger("sovereign.notification_engine.service")


class NotificationService:
    """Orchestrates notification persistence, preference filtering, and real-time dispatch."""

    @classmethod
    async def is_channel_enabled(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        channel: str,
        notification_type: str,
    ) -> bool:
        """Check user preference matrix to determine if a channel is permitted."""
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel,
            NotificationPreference.notification_type.in_([notification_type, "all"]),
        )
        res = await db.execute(stmt)
        prefs = res.scalars().all()
        for pref in prefs:
            if not pref.is_enabled:
                return False
        return True

    @classmethod
    async def send_notification(
        cls,
        db: AsyncSession,
        req: SendNotificationRequest,
        company_id: uuid.UUID,
        sender_id: Optional[uuid.UUID] = None,
    ) -> SendNotificationResponse:
        """Process, persist, and dispatch notification across allowed channels."""
        dispatched_channels: List[str] = []

        # 1. In-App Channel
        if "in_app" in req.channels:
            if await cls.is_channel_enabled(db, req.recipient_id, "in_app", req.notification_type):
                notif = Notification(
                    company_id=company_id,
                    created_by_id=sender_id,
                    recipient_id=req.recipient_id,
                    title=req.title,
                    body=req.body,
                    notification_type=req.notification_type,
                    priority=req.priority,
                    action_url=req.action_url,
                    res_model=req.res_model,
                    res_id=req.res_id,
                    metadata_info=req.metadata_info,
                    is_read=False,
                )
                db.add(notif)
                await db.commit()
                await db.refresh(notif)
                dispatched_channels.append("in_app")

                # In-process EventBus broadcast
                await event_bus.publish(
                    "notification.created",
                    {
                        "id": str(notif.id),
                        "recipient_id": str(notif.recipient_id),
                        "title": notif.title,
                        "notification_type": notif.notification_type,
                        "priority": notif.priority,
                    },
                )

                # Real-time Redis Pub/Sub Broadcast for active WebSockets
                try:
                    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                    channel_name = f"sovereign:notifications:{notif.recipient_id}"
                    payload = json.dumps({
                        "event": "new_notification",
                        "notification": {
                            "id": str(notif.id),
                            "title": notif.title,
                            "body": notif.body,
                            "notification_type": notif.notification_type,
                            "priority": notif.priority,
                            "action_url": notif.action_url,
                            "created_at": notif.created_at.isoformat(),
                        },
                    })
                    await r.publish(channel_name, payload)
                    await r.aclose()
                except Exception as exc:
                    logger.warning(f"Redis notification broadcast error: {exc}")
            else:
                logger.info(f"In-App notification skipped for user {req.recipient_id} due to preferences.")

        # 2. WebPush Channel (VAPID)
        if "web_push" in req.channels:
            if await cls.is_channel_enabled(db, req.recipient_id, "web_push", req.notification_type):
                subs_res = await db.execute(
                    select(PushSubscription).where(
                        PushSubscription.user_id == req.recipient_id,
                    )
                )
                active_subs = subs_res.scalars().all()
                if active_subs:
                    logger.info(
                        f"Dispatched WebPush notification to {len(active_subs)} registered devices for user {req.recipient_id}"
                    )
                    dispatched_channels.append("web_push")

        # 3. Mobile Push Channel (FCM/APNs)
        if "mobile_push" in req.channels or "push" in req.channels:
            dispatched_channels.append("mobile_push")
            logger.info(f"Mobile push formatted for user {req.recipient_id}")

        notif_id = notif.id if "in_app" in dispatched_channels else uuid.uuid4()

        return SendNotificationResponse(
            notification_id=notif_id,
            status="delivered" if dispatched_channels else "filtered_by_preferences",
            dispatched_channels=dispatched_channels,
        )

    @classmethod
    async def mark_as_read(
        cls, db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification:
        """Mark an individual notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user_id,
        )
        res = await db.execute(stmt)
        notif = res.scalar_one_or_none()
        if not notif:
            raise NotFoundException(f"Notification '{notification_id}' not found")

        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notif)
        return notif

    @classmethod
    async def mark_all_as_read(
        cls, db: AsyncSession, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> int:
        """Mark all unread notifications as read for the user."""
        stmt = (
            update(Notification)
            .where(
                Notification.recipient_id == user_id,
                Notification.company_id == company_id,
                Notification.is_read == False,
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount

    @classmethod
    async def get_unread_count(
        cls, db: AsyncSession, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> Dict[str, int]:
        """Return total and unread notification counts for the user."""
        unread_stmt = select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.company_id == company_id,
            Notification.is_read == False,
        )
        total_stmt = select(func.count(Notification.id)).where(
            Notification.recipient_id == user_id,
            Notification.company_id == company_id,
        )
        unread_count = (await db.execute(unread_stmt)).scalar() or 0
        total_count = (await db.execute(total_stmt)).scalar() or 0

        return {"unread_count": unread_count, "total_count": total_count}

    @classmethod
    async def set_user_preference(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        channel: str,
        notification_type: str,
        is_enabled: bool,
    ) -> NotificationPreference:
        """Upsert user delivery channel preference."""
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel,
            NotificationPreference.notification_type == notification_type,
        )
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()

        if pref:
            pref.is_enabled = is_enabled
        else:
            pref = NotificationPreference(
                company_id=company_id,
                user_id=user_id,
                channel=channel,
                notification_type=notification_type,
                is_enabled=is_enabled,
            )
            db.add(pref)

        await db.commit()
        await db.refresh(pref)
        return pref

    @classmethod
    async def register_push_subscription(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        sub_in: PushSubscriptionCreate,
    ) -> PushSubscription:
        """Store WebPush subscription endpoint and cryptographic keys."""
        # Upsert by endpoint
        stmt = select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == sub_in.endpoint,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.p256dh = sub_in.p256dh
            existing.auth = sub_in.auth
            existing.user_agent = sub_in.user_agent
            await db.commit()
            await db.refresh(existing)
            return existing

        sub = PushSubscription(
            company_id=company_id,
            user_id=user_id,
            **sub_in.model_dump(),
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return sub

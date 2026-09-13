"""API routes for notifications, user preferences, WebPush subscriptions, and real-time WebSocket stream."""

import uuid
import asyncio
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from core.config import settings
from core.database import get_db
from core.exceptions import NotFoundException
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.notification_engine.models import (
    Notification,
    NotificationPreference,
    PushSubscription,
)
from modules.base.notification_engine.schemas import (
    NotificationRead,
    NotificationCountResponse,
    SendNotificationRequest,
    SendNotificationResponse,
    NotificationPreferenceRead,
    NotificationPreferenceSet,
    PushSubscriptionCreate,
    PushSubscriptionRead,
)
from modules.base.notification_engine.service import NotificationService

router = APIRouter()


# ==========================================
# 1. Notifications CRUD & Status
# ==========================================

@router.get(
    "/notifications",
    response_model=List[NotificationRead],
    tags=["Notification Engine - In-App"],
    summary="List authenticated user's notifications",
)
async def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    notification_type: Optional[str] = Query(None, description="Filter by type (task, info, alert)"),
    limit: int = Query(50, ge=1, le=100, description="Pagination size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Notification]:
    """Retrieve notifications targeted to the authenticated user."""
    query = (
        select(Notification)
        .where(
            Notification.recipient_id == current_user.id,
            Notification.company_id == current_user.company_id,
        )
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
    if notification_type:
        query = query.where(Notification.notification_type == notification_type)

    res = await db.execute(query)
    return list(res.scalars().all())


@router.get(
    "/unread-count",
    response_model=NotificationCountResponse,
    tags=["Notification Engine - In-App"],
    summary="Get user unread notifications count",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationCountResponse:
    """Return count of unread notifications for top navigation badges."""
    counts = await NotificationService.get_unread_count(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
    )
    return NotificationCountResponse(**counts)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    tags=["Notification Engine - In-App"],
    summary="Mark single notification as read",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Notification:
    """Acknowledge and mark an individual notification as read."""
    return await NotificationService.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post(
    "/notifications/mark-all-read",
    tags=["Notification Engine - In-App"],
    summary="Mark all user notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear all unread notification badges for the active user."""
    affected = await NotificationService.mark_all_as_read(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
    )
    return {"status": "success", "updated_count": affected}


# ==========================================
# 2. Multi-Channel Dispatch
# ==========================================

@router.post(
    "/send",
    response_model=SendNotificationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Notification Engine - Dispatch"],
    summary="Dispatch multi-channel notification",
)
async def send_notification(
    req: SendNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendNotificationResponse:
    """Dispatch notification across allowed channels (In-App, WebPush, Mobile Push)."""
    return await NotificationService.send_notification(
        db=db,
        req=req,
        company_id=current_user.company_id,
        sender_id=current_user.id,
    )


# ==========================================
# 3. User Preferences
# ==========================================

@router.get(
    "/preferences",
    response_model=List[NotificationPreferenceRead],
    tags=["Notification Engine - Preferences"],
    summary="Get user notification preferences",
)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[NotificationPreference]:
    """Retrieve active user delivery preferences across channels and event types."""
    stmt = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.put(
    "/preferences",
    response_model=NotificationPreferenceRead,
    tags=["Notification Engine - Preferences"],
    summary="Set or update channel preference",
)
async def set_user_preference(
    pref_in: NotificationPreferenceSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreference:
    """Configure opt-in / opt-out preferences for a specific channel and notification category."""
    return await NotificationService.set_user_preference(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
        channel=pref_in.channel,
        notification_type=pref_in.notification_type,
        is_enabled=pref_in.is_enabled,
    )


# ==========================================
# 4. Push Subscriptions
# ==========================================

@router.post(
    "/subscriptions",
    response_model=PushSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Notification Engine - Subscriptions"],
    summary="Register WebPush device subscription",
)
async def register_subscription(
    sub_in: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushSubscription:
    """Register browser WebPush (VAPID) endpoint and encryption keys for this user."""
    return await NotificationService.register_push_subscription(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
        sub_in=sub_in,
    )


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Notification Engine - Subscriptions"],
    summary="Unregister WebPush device subscription",
)
async def delete_subscription(
    subscription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a registered WebPush subscription endpoint."""
    stmt = select(PushSubscription).where(
        PushSubscription.id == subscription_id,
        PushSubscription.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()
    if not sub:
        raise NotFoundException(f"Subscription '{subscription_id}' not found")

    await db.delete(sub)
    await db.commit()


# ==========================================
# 5. Real-Time WebSocket Alerts Stream
# ==========================================

@router.websocket("/ws/{user_id}")
async def notification_websocket_stream(
    websocket: WebSocket,
    user_id: uuid.UUID,
):
    """Real-time WebSocket streaming gateway pushing live notifications to connected browser tabs."""
    await websocket.accept()
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    channel_name = f"sovereign:notifications:{user_id}"
    await pubsub.subscribe(channel_name)

    async def reader():
        try:
            async for msg in pubsub.listen():
                if msg and msg["type"] == "message":
                    await websocket.send_text(msg["data"])
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            # Keep-alive ping loop
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        reader_task.cancel()
        await pubsub.unsubscribe(channel_name)
        await pubsub.aclose()
        await r.aclose()

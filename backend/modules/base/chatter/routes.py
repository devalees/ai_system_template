"""API Routes and WebSocket endpoints for Chatter & Activities."""

import uuid
import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from jose import jwt, JWTError

from core.config import settings
from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.chatter.models import MailMessage, Activity
from modules.base.chatter.schemas import (
    MailMessageCreate,
    MailMessageRead,
    ActivityCreate,
    ActivityRead,
)
from modules.base.chatter.service import ChatterService

router = APIRouter()


# ---------------- HTTP Endpoints ----------------

@router.get(
    "/{res_model}/{res_id}/messages",
    response_model=List[MailMessageRead],
    tags=["Chatter Messages"],
    summary="Get chronological chatter message thread for a record",
)
async def get_chatter_thread(
    res_model: str,
    res_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MailMessage]:
    """Retrieve all comments, notifications, and AI agent findings for target record."""
    return await ChatterService.get_messages(
        db=db,
        res_model=res_model,
        res_id=res_id,
        company_id=current_user.company_id,
    )


@router.post(
    "/{res_model}/{res_id}/messages",
    response_model=MailMessageRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Chatter Messages"],
    summary="Post a comment or AI finding to an entity chatter thread",
)
async def post_chatter_message(
    res_model: str,
    res_id: uuid.UUID,
    payload: MailMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MailMessage:
    """Post a new message to the entity thread and broadcast via WebSocket / Redis Pub/Sub."""
    return await ChatterService.post_message(
        db=db,
        res_model=res_model,
        res_id=res_id,
        body=payload.body,
        company_id=current_user.company_id,
        author_id=current_user.id,
        author_type=current_user.user_type,
        message_type=payload.message_type,
        metadata_info=payload.metadata_info,
    )


@router.get(
    "/{res_model}/{res_id}/activities",
    response_model=List[ActivityRead],
    tags=["Chatter Activities"],
    summary="List planned activities for a record",
)
async def get_entity_activities(
    res_model: str,
    res_id: uuid.UUID,
    include_completed: bool = Query(False, description="Include finished activities"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Activity]:
    """List operational todo, calls, and meetings scheduled for an entity."""
    stmt = (
        select(Activity)
        .where(
            Activity.company_id == current_user.company_id,
            Activity.res_model == res_model.lower(),
            Activity.res_id == res_id,
        )
    )
    if not include_completed:
        stmt = stmt.where(Activity.is_completed == False)
    stmt = stmt.order_by(Activity.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/{res_model}/{res_id}/activities",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Chatter Activities"],
    summary="Schedule an activity for a record",
)
async def schedule_entity_activity(
    res_model: str,
    res_id: uuid.UUID,
    payload: ActivityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Activity:
    """Schedule a new task or deadline anchored to an entity."""
    return await ChatterService.schedule_activity(
        db=db,
        res_model=res_model,
        res_id=res_id,
        summary=payload.summary,
        company_id=current_user.company_id,
        activity_type=payload.activity_type,
        assigned_to_id=payload.assigned_to_id,
        due_date=payload.due_date,
    )


@router.patch(
    "/activities/{activity_id}/complete",
    response_model=ActivityRead,
    tags=["Chatter Activities"],
    summary="Complete a scheduled activity",
)
async def complete_activity_endpoint(
    activity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Activity:
    """Mark scheduled activity as completed and log resolution to the thread."""
    try:
        return await ChatterService.complete_activity(
            db=db,
            activity_id=activity_id,
            company_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------- WebSocket Real-time Endpoint ----------------

@router.websocket("/ws/{res_model}/{res_id}")
async def chatter_websocket_endpoint(
    websocket: WebSocket,
    res_model: str,
    res_id: uuid.UUID,
    token: Optional[str] = Query(None),
):
    """Subscribe to real-time chatter messages for an entity via Redis Pub/Sub."""
    await websocket.accept()

    # Authenticate token
    company_id: Optional[uuid.UUID] = None
    if token:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            company_id_str = payload.get("company_id")
            if company_id_str:
                company_id = uuid.UUID(company_id_str)
        except (JWTError, ValueError):
            pass

    if not company_id:
        await websocket.send_json({"error": "Authentication required."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    channel = f"sovereign:chatter:{company_id}:{res_model.lower()}:{res_id}"
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    async def listener():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    task = asyncio.create_task(listener())

    try:
        while True:
            # Keep connection alive receiving ping or messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await r.aclose()

"""Database models for notifications, preferences, and push subscriptions."""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class Notification(BaseModel):
    """In-app and multi-channel notification record."""
    __tablename__ = "notifications"

    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), default="info", nullable=False, index=True)  # info | warning | success | danger | task | mention | ai_alert
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)  # low | normal | high | urgent
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    res_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class NotificationPreference(BaseModel):
    """Per-user delivery preference for channels and notification types."""
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # in_app | email | web_push | sms
    notification_type: Mapped[str] = mapped_column(String(50), default="all", nullable=False, index=True)  # all | task | mention | invoice | alert
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PushSubscription(BaseModel):
    """WebPush (VAPID) client device subscription record."""
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

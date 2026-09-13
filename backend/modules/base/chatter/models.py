"""Database models for polymorphic chatter threads and scheduled activities."""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class MailMessage(BaseModel):
    """Polymorphic discussion comment, notification, or AI agent analytical finding."""
    __tablename__ = "chatter_messages"

    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    res_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="comment", nullable=False, index=True)  # comment | notification | ai_finding | activity
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    author_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False)  # human | ai_agent | system
    metadata_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Activity(BaseModel):
    """Planned operational task or deadline anchored to an entity record."""
    __tablename__ = "chatter_activities"

    res_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    res_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), default="todo", nullable=False)  # todo | call | meeting | review
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

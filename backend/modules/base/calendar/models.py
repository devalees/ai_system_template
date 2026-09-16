"""SQLAlchemy models for Company Calendar & Recurring Events."""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.identity_rbac.models import User
from modules.base.parties.models import PartyContact


class CalendarEvent(BaseModel):
    """Represents a scheduled calendar event, appointment, or meeting."""

    __tablename__ = "calendar_events"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # RFC 5545 RRULE string (e.g. "FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10")
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(500), default=None, nullable=True)

    # Optional polymorphic linkage to any business record (e.g. party, task, contract, workflow)
    res_model: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True, index=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), default=None, nullable=True, index=True
    )

    # Organizer
    organizer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    location: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="confirmed", nullable=False)  # confirmed, tentative, cancelled
    color: Mapped[Optional[str]] = mapped_column(String(50), default="#3B82F6", nullable=True)

    # Relationships
    organizer: Mapped[Optional[User]] = relationship("User", foreign_keys=[organizer_id], lazy="selectin")
    attendees: Mapped[List["EventAttendee"]] = relationship(
        "EventAttendee",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_calendar_events_tenant_time", "company_id", "start_time", "end_time"),
        Index("ix_calendar_events_tenant_res", "company_id", "res_model", "res_id"),
    )


class EventAttendee(BaseModel):
    """Attendee or participant invited to a CalendarEvent."""

    __tablename__ = "calendar_event_attendees"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    party_contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("party_contacts.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(150), default=None, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), default=None, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="needs_action", nullable=False)  # needs_action, accepted, declined, tentative
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)

    # Relationships
    event: Mapped["CalendarEvent"] = relationship("CalendarEvent", back_populates="attendees")
    user: Mapped[Optional[User]] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    party_contact: Mapped[Optional[PartyContact]] = relationship("PartyContact", foreign_keys=[party_contact_id], lazy="selectin")

    __table_args__ = (
        Index("ix_calendar_attendees_tenant_event_user", "company_id", "event_id", "user_id"),
    )

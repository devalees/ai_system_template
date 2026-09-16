"""Pydantic schemas and DTOs for Company Calendar & Recurring Events."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from dateutil.rrule import rrulestr


class AttendeeBase(BaseModel):
    user_id: Optional[uuid.UUID] = Field(None, description="Internal system user ID")
    party_contact_id: Optional[uuid.UUID] = Field(None, description="External party representative contact ID")
    name: Optional[str] = Field(None, max_length=150, description="Attendee display name")
    email: Optional[str] = Field(None, max_length=150, description="Attendee email address")
    status: Optional[str] = Field("needs_action", description="RSVP status (needs_action, accepted, declined, tentative)")
    notes: Optional[str] = Field(None, description="Optional RSVP message or notes")


class AttendeeCreate(AttendeeBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sarah Connor",
                "email": "sarah@cyberdyne.com",
                "status": "needs_action",
            }
        }
    )


class AttendeeRSVPUpdate(BaseModel):
    status: str = Field(..., pattern="^(needs_action|accepted|declined|tentative)$", description="Updated RSVP status")
    notes: Optional[str] = Field(None, description="RSVP note or decline reason")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "accepted",
                "notes": "Will attend in person.",
            }
        }
    )


class AttendeeResponse(AttendeeBase):
    id: uuid.UUID
    company_id: uuid.UUID
    event_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarEventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Event title or subject")
    description: Optional[str] = Field(None, description="Detailed agenda or notes")
    start_time: datetime = Field(..., description="Event start timestamp (with timezone)")
    end_time: datetime = Field(..., description="Event end timestamp (with timezone)")
    is_all_day: bool = Field(False, description="Whether event spans full day")
    recurrence_rule: Optional[str] = Field(
        None,
        max_length=500,
        description="RFC 5545 RRULE string (e.g. 'FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10')",
    )
    res_model: Optional[str] = Field(None, max_length=100, description="Linked entity model name (e.g. 'parties')")
    res_id: Optional[uuid.UUID] = Field(None, description="Linked entity record ID")
    location: Optional[str] = Field(None, max_length=255, description="Meeting location or URL")
    status: Optional[str] = Field("confirmed", max_length=50, description="confirmed, tentative, cancelled")
    color: Optional[str] = Field("#3B82F6", max_length=50, description="UI calendar display color")
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CalendarEventCreate(CalendarEventBase):
    attendees: Optional[List[AttendeeCreate]] = Field(default_factory=list, description="Initial invitees")

    @model_validator(mode="after")
    def validate_event_times_and_recurrence(self) -> "CalendarEventCreate":
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        if self.recurrence_rule:
            rule_str = self.recurrence_rule.strip()
            if not rule_str.startswith("RRULE:"):
                rule_str = f"RRULE:{rule_str}"
            try:
                rrulestr(rule_str, dtstart=self.start_time)
            except Exception as e:
                raise ValueError(f"Invalid RFC 5545 RRULE syntax: {str(e)}")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Quarterly Business Review",
                "description": "Executive review of Q3 financials and roadmap.",
                "start_time": "2026-10-01T09:00:00Z",
                "end_time": "2026-10-01T11:00:00Z",
                "is_all_day": False,
                "recurrence_rule": "FREQ=MONTHLY;INTERVAL=3;COUNT=4",
                "location": "Boardroom A & Google Meet",
                "status": "confirmed",
                "color": "#10B981",
                "attendees": [
                    {"name": "Ehab CEO", "email": "ehab@sovereign.io", "status": "accepted"}
                ],
            }
        }
    )


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    res_model: Optional[str] = None
    res_id: Optional[uuid.UUID] = None
    location: Optional[str] = None
    status: Optional[str] = None
    color: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_times(self) -> "CalendarEventUpdate":
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        if self.recurrence_rule:
            rule_str = self.recurrence_rule.strip()
            if not rule_str.startswith("RRULE:"):
                rule_str = f"RRULE:{rule_str}"
            try:
                rrulestr(rule_str)
            except Exception as e:
                raise ValueError(f"Invalid RFC 5545 RRULE syntax: {str(e)}")
        return self


class CalendarEventResponse(CalendarEventBase):
    id: uuid.UUID
    company_id: uuid.UUID
    organizer_id: Optional[uuid.UUID] = None
    attendees: List[AttendeeResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarOccurrenceResponse(BaseModel):
    """Represents a computed single occurrence of a recurring or single event."""
    occurrence_id: str
    event_id: uuid.UUID
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    is_recurring_instance: bool = False
    location: Optional[str] = None
    status: str
    color: Optional[str] = None
    organizer_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class CalendarImportICSRequest(BaseModel):
    ics_content: str = Field(..., description="Raw RFC 5545 iCalendar (.ics) string data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ics_content": "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:Board Meeting\nDTSTART:20261001T090000Z\nDTEND:20261001T100000Z\nEND:VEVENT\nEND:VCALENDAR"
            }
        }
    )

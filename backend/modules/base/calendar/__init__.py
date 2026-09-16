"""Company Calendar & Recurring Events Module."""

from modules.base.calendar.models import CalendarEvent, EventAttendee
from modules.base.calendar.service import CalendarService

__all__ = [
    "CalendarEvent",
    "EventAttendee",
    "CalendarService",
]

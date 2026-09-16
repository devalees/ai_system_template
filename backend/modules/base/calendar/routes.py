"""FastAPI route endpoints for Company Calendar & Recurring Events."""

import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from core.exceptions import ValidationException
from modules.base.identity_rbac.models import User
from modules.base.identity_rbac.dependencies import get_current_user

from modules.base.calendar.service import CalendarService
from modules.base.calendar.schemas import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
    CalendarOccurrenceResponse,
    AttendeeCreate,
    AttendeeRSVPUpdate,
    AttendeeResponse,
    CalendarImportICSRequest,
)

router = APIRouter(prefix="", tags=["Company Calendar & Events"])


def _resolve_company_id(user: User) -> uuid.UUID:
    """Resolve active company context."""
    cid = get_active_company_id() or user.company_id
    if not cid:
        raise ValidationException("Active company context (X-Company-ID) is required.")
    return cid


# ---------------------------------------------------------------------------
# Calendar Events Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Calendar Event",
    description="Creates a new calendar event, appointment, or recurring meeting with optional initial invitees.",
)
async def create_event(
    payload: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarEventResponse:
    company_id = _resolve_company_id(user)
    event = await CalendarService.create_event(db, company_id, user.id, payload)
    return CalendarEventResponse.model_validate(event)


@router.get(
    "/events",
    response_model=List[CalendarEventResponse],
    summary="List Calendar Events",
    description="Lists calendar events matching optional date range, entity link, or organizer criteria.",
)
async def list_events(
    start_date: Optional[datetime] = Query(None, description="Filter events ending on or after this timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter events starting on or before this timestamp"),
    res_model: Optional[str] = Query(None, description="Filter by attached record entity model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by attached record entity ID"),
    organizer_id: Optional[uuid.UUID] = Query(None, description="Filter by event organizer"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CalendarEventResponse]:
    company_id = _resolve_company_id(user)
    events = await CalendarService.list_events(
        db,
        company_id,
        start_date=start_date,
        end_date=end_date,
        res_model=res_model,
        res_id=res_id,
        organizer_id=organizer_id,
        limit=limit,
        offset=offset,
    )
    return [CalendarEventResponse.model_validate(evt) for evt in events]


@router.get(
    "/occurrences",
    response_model=List[CalendarOccurrenceResponse],
    summary="Expand Calendar Occurrences",
    description="Expands recurring and non-recurring events into concrete instances within a specified time window.",
)
async def list_occurrences(
    start_date: datetime = Query(..., description="Start of occurrence search window"),
    end_date: datetime = Query(..., description="End of occurrence search window"),
    res_model: Optional[str] = Query(None, description="Filter by attached record model"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by attached record ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CalendarOccurrenceResponse]:
    if end_date < start_date:
        raise ValidationException("end_date must be greater than or equal to start_date")

    company_id = _resolve_company_id(user)
    events = await CalendarService.list_events(
        db,
        company_id,
        start_date=start_date,
        end_date=end_date,
        res_model=res_model,
        res_id=res_id,
        limit=500,
    )
    return CalendarService.expand_occurrences(events, start_date, end_date)


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
    summary="Get Calendar Event Details",
    description="Retrieves a specific calendar event along with attendee list.",
)
async def get_event(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarEventResponse:
    company_id = _resolve_company_id(user)
    event = await CalendarService.get_event(db, company_id, event_id)
    return CalendarEventResponse.model_validate(event)


@router.put(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
    summary="Update Calendar Event",
    description="Updates details, schedule, or recurrence rule of an existing event.",
)
async def update_event(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    payload: CalendarEventUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarEventResponse:
    company_id = _resolve_company_id(user)
    event = await CalendarService.update_event(db, company_id, event_id, payload)
    return CalendarEventResponse.model_validate(event)


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Calendar Event",
    description="Deletes a calendar event and its attendee invites.",
)
async def delete_event(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await CalendarService.delete_event(db, company_id, event_id)


# ---------------------------------------------------------------------------
# Attendee & RSVP Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/events/{event_id}/attendees",
    response_model=AttendeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Event Attendee",
    description="Adds a user, party contact, or external participant to an event.",
)
async def add_attendee(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    payload: AttendeeCreate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttendeeResponse:
    company_id = _resolve_company_id(user)
    attendee = await CalendarService.add_attendee(db, company_id, event_id, payload)
    return AttendeeResponse.model_validate(attendee)


@router.put(
    "/events/{event_id}/attendees/{attendee_id}/rsvp",
    response_model=AttendeeResponse,
    summary="Update Attendee RSVP Status",
    description="Updates RSVP response (accepted, declined, tentative, needs_action) and optional notes.",
)
async def update_attendee_rsvp(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    attendee_id: uuid.UUID = Path(..., description="Attendee record ID"),
    payload: AttendeeRSVPUpdate = ...,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttendeeResponse:
    company_id = _resolve_company_id(user)
    attendee = await CalendarService.update_attendee_rsvp(db, company_id, event_id, attendee_id, payload)
    return AttendeeResponse.model_validate(attendee)


@router.delete(
    "/events/{event_id}/attendees/{attendee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Event Attendee",
    description="Removes an attendee from an event.",
)
async def remove_attendee(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    attendee_id: uuid.UUID = Path(..., description="Attendee record ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    company_id = _resolve_company_id(user)
    await CalendarService.remove_attendee(db, company_id, event_id, attendee_id)


# ---------------------------------------------------------------------------
# RFC 5545 iCalendar Import & Export
# ---------------------------------------------------------------------------

@router.get(
    "/events/{event_id}/export.ics",
    summary="Export Event as iCalendar (.ics)",
    description="Generates and downloads standard RFC 5545 iCalendar format file for Outlook, Google Calendar, or Apple Calendar.",
)
async def export_event_ics(
    event_id: uuid.UUID = Path(..., description="Calendar event ID"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    company_id = _resolve_company_id(user)
    event = await CalendarService.get_event(db, company_id, event_id)
    ics_text = CalendarService.export_ics(event)
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="event_{event.id}.ics"'
        },
    )


@router.post(
    "/events/import-ics",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import iCalendar (.ics) Event",
    description="Parses RFC 5545 iCalendar data and creates an event with recurrence and invitees.",
)
async def import_event_ics(
    payload: CalendarImportICSRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarEventResponse:
    company_id = _resolve_company_id(user)
    event = await CalendarService.import_ics(db, company_id, user.id, payload.ics_content)
    return CalendarEventResponse.model_validate(event)

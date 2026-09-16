"""Business domain service for Company Calendar & Recurring Events."""

import uuid
import re
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from dateutil.rrule import rrulestr
from dateutil.parser import parse as parse_date

from core.exceptions import EntityNotFoundException, ValidationException
from core.event_bus import event_bus
from modules.base.identity_rbac.models import User
from modules.base.parties.models import PartyContact
from modules.base.calendar.models import CalendarEvent, EventAttendee
from modules.base.calendar.schemas import (
    CalendarEventCreate,
    CalendarEventUpdate,
    AttendeeCreate,
    AttendeeRSVPUpdate,
    CalendarOccurrenceResponse,
)

logger = logging.getLogger("sovereign.calendar")


class CalendarService:
    """Service encapsulating calendar scheduling, recurring event expansion, and RFC 5545 iCalendar serialization."""

    @staticmethod
    def _format_ics_datetime(dt: datetime) -> str:
        """Format datetime into RFC 5545 UTC compact format (YYYYMMDDTHHMMSSZ)."""
        if dt.tzinfo is not None:
            utc_dt = dt.astimezone(timezone.utc)
        else:
            utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt.strftime("%Y%m%dT%H%M%SZ")

    @classmethod
    async def create_event(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        data: CalendarEventCreate,
    ) -> CalendarEvent:
        """Create a new calendar event with optional attendees and recurrence rules."""
        event = CalendarEvent(
            company_id=company_id,
            organizer_id=user_id,
            title=data.title,
            description=data.description,
            start_time=data.start_time,
            end_time=data.end_time,
            is_all_day=data.is_all_day,
            recurrence_rule=data.recurrence_rule,
            res_model=data.res_model,
            res_id=data.res_id,
            location=data.location,
            status=data.status or "confirmed",
            color=data.color or "#3B82F6",
            custom_fields=data.custom_fields or {},
        )
        db.add(event)
        await db.flush()

        # Process initial invitees
        if data.attendees:
            for att_data in data.attendees:
                attendee = await cls._prepare_attendee(db, company_id, event.id, att_data)
                db.add(attendee)

        await db.commit()
        await db.refresh(event)

        # Notify via EventBus
        try:
            await event_bus.publish(
                "calendar.event_created",
                {
                    "event_id": str(event.id),
                    "title": event.title,
                    "company_id": str(company_id),
                    "organizer_id": str(user_id) if user_id else None,
                    "start_time": event.start_time.isoformat(),
                },
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")
        return event

    @classmethod
    async def _prepare_attendee(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
        data: AttendeeCreate,
    ) -> EventAttendee:
        """Helper to resolve attendee name/email from User or PartyContact if not explicitly specified."""
        name = data.name
        email = data.email

        if data.user_id and (not name or not email):
            user = await db.get(User, data.user_id)
            if user:
                name = name or user.full_name or user.username
                email = email or user.email

        if data.party_contact_id and (not name or not email):
            contact = await db.get(PartyContact, data.party_contact_id)
            if contact:
                name = name or contact.name
                email = email or contact.email

        return EventAttendee(
            company_id=company_id,
            event_id=event_id,
            user_id=data.user_id,
            party_contact_id=data.party_contact_id,
            name=name,
            email=email,
            status=data.status or "needs_action",
            notes=data.notes,
        )

    @classmethod
    async def get_event(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> CalendarEvent:
        """Fetch a specific event by ID within the current tenant."""
        stmt = select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.company_id == company_id,
        )
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()
        if not event:
            raise EntityNotFoundException("CalendarEvent", event_id)
        return event

    @classmethod
    async def update_event(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
        data: CalendarEventUpdate,
    ) -> CalendarEvent:
        """Update an existing calendar event."""
        event = await cls.get_event(db, company_id, event_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(event, field, value)

        # Re-verify time validity
        if event.end_time < event.start_time:
            raise ValidationException("end_time must be greater than or equal to start_time")

        await db.commit()
        await db.refresh(event)

        try:
            await event_bus.publish(
                "calendar.event_updated",
                {"event_id": str(event.id), "company_id": str(company_id)},
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")
        return event

    @classmethod
    async def delete_event(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> None:
        """Delete a calendar event."""
        event = await cls.get_event(db, company_id, event_id)
        await db.delete(event)
        await db.commit()

        try:
            await event_bus.publish(
                "calendar.event_deleted",
                {"event_id": str(event_id), "company_id": str(company_id)},
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")

    @classmethod
    async def list_events(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
        organizer_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CalendarEvent]:
        """List raw calendar events matching optional filter criteria."""
        conditions = [CalendarEvent.company_id == company_id]

        if res_model:
            conditions.append(CalendarEvent.res_model == res_model)
        if res_id:
            conditions.append(CalendarEvent.res_id == res_id)
        if organizer_id:
            conditions.append(CalendarEvent.organizer_id == organizer_id)

        if start_date and end_date:
            # Match non-recurring events within window OR any recurring event that started on or before end_date
            conditions.append(
                or_(
                    and_(
                        CalendarEvent.recurrence_rule.is_(None),
                        CalendarEvent.end_time >= start_date,
                        CalendarEvent.start_time <= end_date,
                    ),
                    and_(
                        CalendarEvent.recurrence_rule.isnot(None),
                        CalendarEvent.start_time <= end_date,
                    ),
                )
            )
        elif start_date:
            conditions.append(CalendarEvent.end_time >= start_date)
        elif end_date:
            conditions.append(CalendarEvent.start_time <= end_date)

        stmt = (
            select(CalendarEvent)
            .where(and_(*conditions))
            .order_by(CalendarEvent.start_time.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    def expand_occurrences(
        cls,
        events: List[CalendarEvent],
        window_start: datetime,
        window_end: datetime,
    ) -> List[CalendarOccurrenceResponse]:
        """Expand recurring events into concrete occurrence instances within the requested time window."""
        results: List[CalendarOccurrenceResponse] = []

        # Standardize window timezone
        target_tz = timezone.utc
        if window_start.tzinfo is None:
            w_start = window_start.replace(tzinfo=target_tz)
        else:
            w_start = window_start.astimezone(target_tz)

        if window_end.tzinfo is None:
            w_end = window_end.replace(tzinfo=target_tz)
        else:
            w_end = window_end.astimezone(target_tz)

        for event in events:
            evt_start = event.start_time if event.start_time.tzinfo else event.start_time.replace(tzinfo=target_tz)
            evt_end = event.end_time if event.end_time.tzinfo else event.end_time.replace(tzinfo=target_tz)
            duration = evt_end - evt_start

            if not event.recurrence_rule:
                # Non-recurring event: check overlap
                if evt_end >= w_start and evt_start <= w_end:
                    results.append(
                        CalendarOccurrenceResponse(
                            occurrence_id=str(event.id),
                            event_id=event.id,
                            title=event.title,
                            description=event.description,
                            start_time=evt_start,
                            end_time=evt_end,
                            is_all_day=event.is_all_day,
                            is_recurring_instance=False,
                            location=event.location,
                            status=event.status,
                            color=event.color,
                            organizer_id=event.organizer_id,
                        )
                    )
            else:
                # Recurring event: compute occurrences via dateutil.rrule
                rule_str = event.recurrence_rule.strip()
                if not rule_str.startswith("RRULE:"):
                    rule_str = f"RRULE:{rule_str}"
                try:
                    rule = rrulestr(rule_str, dtstart=evt_start)
                    occurrences = rule.between(w_start, w_end, inc=True)
                    for occ_start in occurrences:
                        occ_end = occ_start + duration
                        occ_key = f"{event.id}_{occ_start.strftime('%Y%m%dT%H%M%SZ')}"
                        results.append(
                            CalendarOccurrenceResponse(
                                occurrence_id=occ_key,
                                event_id=event.id,
                                title=event.title,
                                description=event.description,
                                start_time=occ_start,
                                end_time=occ_end,
                                is_all_day=event.is_all_day,
                                is_recurring_instance=True,
                                location=event.location,
                                status=event.status,
                                color=event.color,
                                organizer_id=event.organizer_id,
                            )
                        )
                except Exception:
                    # Fallback if corrupted RRULE: include master if it intersects
                    if evt_end >= w_start and evt_start <= w_end:
                        results.append(
                            CalendarOccurrenceResponse(
                                occurrence_id=str(event.id),
                                event_id=event.id,
                                title=event.title,
                                description=event.description,
                                start_time=evt_start,
                                end_time=evt_end,
                                is_all_day=event.is_all_day,
                                is_recurring_instance=False,
                                location=event.location,
                                status=event.status,
                                color=event.color,
                                organizer_id=event.organizer_id,
                            )
                        )

        results.sort(key=lambda x: x.start_time)
        return results

    @classmethod
    async def add_attendee(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
        data: AttendeeCreate,
    ) -> EventAttendee:
        """Add an attendee to an existing event."""
        event = await cls.get_event(db, company_id, event_id)
        attendee = await cls._prepare_attendee(db, company_id, event.id, data)
        db.add(attendee)
        await db.commit()
        await db.refresh(attendee)

        try:
            await event_bus.publish(
                "calendar.attendee_added",
                {
                    "event_id": str(event.id),
                    "attendee_id": str(attendee.id),
                    "email": attendee.email,
                },
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")
        return attendee

    @classmethod
    async def update_attendee_rsvp(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
        attendee_id: uuid.UUID,
        data: AttendeeRSVPUpdate,
    ) -> EventAttendee:
        """Update an attendee's RSVP response status."""
        stmt = select(EventAttendee).where(
            EventAttendee.id == attendee_id,
            EventAttendee.event_id == event_id,
            EventAttendee.company_id == company_id,
        )
        res = await db.execute(stmt)
        attendee = res.scalar_one_or_none()
        if not attendee:
            raise EntityNotFoundException("EventAttendee", attendee_id)

        attendee.status = data.status
        if data.notes is not None:
            attendee.notes = data.notes

        await db.commit()
        await db.refresh(attendee)

        try:
            await event_bus.publish(
                "calendar.rsvp_updated",
                {
                    "event_id": str(event_id),
                    "attendee_id": str(attendee.id),
                    "status": attendee.status,
                },
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")
        return attendee

    @classmethod
    async def remove_attendee(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        event_id: uuid.UUID,
        attendee_id: uuid.UUID,
    ) -> None:
        """Remove an attendee from an event."""
        stmt = select(EventAttendee).where(
            EventAttendee.id == attendee_id,
            EventAttendee.event_id == event_id,
            EventAttendee.company_id == company_id,
        )
        res = await db.execute(stmt)
        attendee = res.scalar_one_or_none()
        if not attendee:
            raise EntityNotFoundException("EventAttendee", attendee_id)

        await db.delete(attendee)
        await db.commit()

        try:
            await event_bus.publish(
                "calendar.attendee_removed",
                {"event_id": str(event_id), "attendee_id": str(attendee_id)},
            )
        except Exception as exc:
            logger.warning(f"Calendar EventBus publish failed: {exc}")

    @classmethod
    def export_ics(cls, event: CalendarEvent) -> str:
        """Generate standard RFC 5545 iCalendar (.ics) string for an event."""
        now_str = cls._format_ics_datetime(datetime.now(timezone.utc))
        dtstart_str = cls._format_ics_datetime(event.start_time)
        dtend_str = cls._format_ics_datetime(event.end_time)

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Sovereign Platform//Calendar Engine v1.0//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{event.id}@sovereign.platform",
            f"DTSTAMP:{now_str}",
            f"DTSTART:{dtstart_str}",
            f"DTEND:{dtend_str}",
            f"SUMMARY:{event.title}",
        ]

        if event.description:
            clean_desc = event.description.replace("\n", "\\n")
            lines.append(f"DESCRIPTION:{clean_desc}")

        if event.location:
            lines.append(f"LOCATION:{event.location}")

        lines.append(f"STATUS:{event.status.upper()}")

        if event.recurrence_rule:
            rrule_val = event.recurrence_rule.strip()
            if rrule_val.startswith("RRULE:"):
                rrule_val = rrule_val[6:]
            lines.append(f"RRULE:{rrule_val}")

        for att in event.attendees:
            partstat = att.status.upper().replace("_", "-")
            name_part = f";CN={att.name}" if att.name else ""
            email_part = att.email or f"{att.id}@sovereign.internal"
            lines.append(f"ATTENDEE{name_part};PARTSTAT={partstat}:mailto:{email_part}")

        lines.append("END:VEVENT")
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    @classmethod
    async def import_ics(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        ics_content: str,
    ) -> CalendarEvent:
        """Parse RFC 5545 iCalendar string and instantiate a CalendarEvent."""
        title = "Imported Event"
        description = None
        location = None
        start_time = None
        end_time = None
        recurrence_rule = None
        attendees: List[AttendeeCreate] = []

        lines = ics_content.replace("\r", "").split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("SUMMARY:"):
                title = line[8:].strip()
            elif line.startswith("DESCRIPTION:"):
                description = line[12:].replace("\\n", "\n").strip()
            elif line.startswith("LOCATION:"):
                location = line[9:].strip()
            elif line.startswith("DTSTART:") or line.startswith("DTSTART;"):
                val = line.split(":", 1)[1].strip()
                try:
                    start_time = parse_date(val)
                except Exception:
                    pass
            elif line.startswith("DTEND:") or line.startswith("DTEND;"):
                val = line.split(":", 1)[1].strip()
                try:
                    end_time = parse_date(val)
                except Exception:
                    pass
            elif line.startswith("RRULE:"):
                recurrence_rule = line[6:].strip()
            elif line.startswith("ATTENDEE"):
                # ATTENDEE;CN=Name:mailto:email
                match_email = re.search(r"mailto:([^\s;]+)", line, re.IGNORECASE)
                match_cn = re.search(r"CN=([^;:]+)", line)
                att_email = match_email.group(1) if match_email else None
                att_name = match_cn.group(1) if match_cn else (att_email or "Attendee")
                if att_email:
                    attendees.append(AttendeeCreate(name=att_name, email=att_email))

        if not start_time:
            start_time = datetime.now(timezone.utc)
        if not end_time:
            end_time = start_time

        # Ensure tz-awareness
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        data = CalendarEventCreate(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location=location,
            recurrence_rule=recurrence_rule,
            attendees=attendees,
        )
        return await cls.create_event(db, company_id, user_id, data)

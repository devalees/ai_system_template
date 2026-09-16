"""Comprehensive unit and integration tests for Company Calendar & Recurring Events."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_calendar_event_crud_and_tenant_isolation(db_session: AsyncSession):
    """Verify event creation, listing, updating, deletion, and strict multi-tenancy isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Setup Company A & Company B
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Company Alpha", code=f"CA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Company Beta", code=f"CB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A in Company A
        user_a_name = f"user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a_name}@test.com", "username": user_a_name, "password": "Password123!", "full_name": "User Alpha", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a_name, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B in Company B
        user_b_name = f"user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b_name}@test.com", "username": user_b_name, "password": "Password123!", "full_name": "User Beta", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b_name, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 2. Company A creates an event
        event_payload = {
            "title": "Alpha Board Sync",
            "description": "Annual strategy sync",
            "start_time": "2026-10-15T09:00:00Z",
            "end_time": "2026-10-15T11:00:00Z",
            "is_all_day": False,
            "location": "HQ Conference Room 1",
            "status": "confirmed",
            "color": "#3B82F6",
        }
        res_create = await client.post("/api/v1/calendar/events", json=event_payload, headers=headers_a)
        assert res_create.status_code == 201, res_create.text
        event_data = res_create.json()
        event_id = event_data["id"]
        assert event_data["title"] == "Alpha Board Sync"
        assert event_data["company_id"] == str(comp_a)

        # 3. Company A lists events
        res_list_a = await client.get("/api/v1/calendar/events", headers=headers_a)
        assert res_list_a.status_code == 200
        assert len(res_list_a.json()) == 1

        # 4. Company B lists events -> must see 0 events (isolation)
        res_list_b = await client.get("/api/v1/calendar/events", headers=headers_b)
        assert res_list_b.status_code == 200
        assert len(res_list_b.json()) == 0

        # 5. Company B attempts to fetch Company A's event -> 404
        res_get_b = await client.get(f"/api/v1/calendar/events/{event_id}", headers=headers_b)
        assert res_get_b.status_code == 404

        # 6. Company A updates event
        res_update = await client.put(
            f"/api/v1/calendar/events/{event_id}",
            json={"title": "Alpha Board Sync (Updated)", "location": "Boardroom Deluxe"},
            headers=headers_a,
        )
        assert res_update.status_code == 200
        assert res_update.json()["title"] == "Alpha Board Sync (Updated)"
        assert res_update.json()["location"] == "Boardroom Deluxe"

        # 7. Company A deletes event
        res_del = await client.delete(f"/api/v1/calendar/events/{event_id}", headers=headers_a)
        assert res_del.status_code == 204

        # 8. Verify event is gone
        res_get_gone = await client.get(f"/api/v1/calendar/events/{event_id}", headers=headers_a)
        assert res_get_gone.status_code == 404


@pytest.mark.asyncio
async def test_calendar_recurrence_expansion(db_session: AsyncSession):
    """Verify RFC 5545 RRULE expansion into discrete occurrences."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Recurrence Test Co", code=f"RC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"rec_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Recurrence Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create daily recurring event with 5 occurrences
        payload = {
            "title": "Daily Standup",
            "start_time": "2026-10-01T09:00:00Z",
            "end_time": "2026-10-01T09:30:00Z",
            "is_all_day": False,
            "recurrence_rule": "FREQ=DAILY;COUNT=5",
            "location": "Online Huddle",
        }
        res_create = await client.post("/api/v1/calendar/events", json=payload, headers=headers)
        assert res_create.status_code == 201, res_create.text
        event_id = res_create.json()["id"]

        # 1. Expand occurrences inside window (Oct 1 to Oct 10)
        res_occ = await client.get(
            "/api/v1/calendar/occurrences?start_date=2026-10-01T00:00:00Z&end_date=2026-10-10T23:59:59Z",
            headers=headers,
        )
        assert res_occ.status_code == 200, res_occ.text
        occurrences = res_occ.json()
        assert len(occurrences) == 5

        for i, occ in enumerate(occurrences):
            assert occ["event_id"] == event_id
            assert occ["title"] == "Daily Standup"
            assert occ["is_recurring_instance"] is True
            # Expected date: Oct 1 + i days
            expected_day = f"2026-10-0{i + 1}"
            assert occ["start_time"].startswith(expected_day)

        # 2. Window outside recurrence range (November 2026) -> 0 occurrences
        res_empty = await client.get(
            "/api/v1/calendar/occurrences?start_date=2026-11-01T00:00:00Z&end_date=2026-11-10T23:59:59Z",
            headers=headers,
        )
        assert res_empty.status_code == 200
        assert len(res_empty.json()) == 0


@pytest.mark.asyncio
async def test_calendar_attendees_and_rsvp(db_session: AsyncSession):
    """Verify attendee management and RSVP responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Attendee Test Co", code=f"AT_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"att_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Attendee Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create event with initial attendee
        payload = {
            "title": "Client Discovery Session",
            "start_time": "2026-10-20T14:00:00Z",
            "end_time": "2026-10-20T15:00:00Z",
            "attendees": [
                {"name": "Alice Partner", "email": "alice@partner.com", "status": "needs_action"}
            ],
        }
        res_create = await client.post("/api/v1/calendar/events", json=payload, headers=headers)
        assert res_create.status_code == 201, res_create.text
        event = res_create.json()
        event_id = event["id"]
        assert len(event["attendees"]) == 1

        # 2. Add second attendee
        res_add = await client.post(
            f"/api/v1/calendar/events/{event_id}/attendees",
            json={"name": "Bob Advisor", "email": "bob@advisor.com", "status": "needs_action"},
            headers=headers,
        )
        assert res_add.status_code == 201, res_add.text
        bob_att = res_add.json()
        bob_id = bob_att["id"]

        # Verify event now has 2 attendees
        res_get = await client.get(f"/api/v1/calendar/events/{event_id}", headers=headers)
        assert len(res_get.json()["attendees"]) == 2

        # 3. Bob updates RSVP to accepted
        res_rsvp = await client.put(
            f"/api/v1/calendar/events/{event_id}/attendees/{bob_id}/rsvp",
            json={"status": "accepted", "notes": "Joining via Zoom link."},
            headers=headers,
        )
        assert res_rsvp.status_code == 200, res_rsvp.text
        assert res_rsvp.json()["status"] == "accepted"
        assert res_rsvp.json()["notes"] == "Joining via Zoom link."

        # 4. Remove Bob from attendees
        res_rm = await client.delete(f"/api/v1/calendar/events/{event_id}/attendees/{bob_id}", headers=headers)
        assert res_rm.status_code == 204

        # Verify event now has 1 attendee
        res_final = await client.get(f"/api/v1/calendar/events/{event_id}", headers=headers)
        assert len(res_final.json()["attendees"]) == 1


@pytest.mark.asyncio
async def test_calendar_icalendar_export_and_import(db_session: AsyncSession):
    """Verify RFC 5545 iCalendar (.ics) export and import capabilities."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="ICS Test Co", code=f"IC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"ics_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "ICS Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create event for export
        event_payload = {
            "title": "Global Partner Summit",
            "description": "Annual summit for regional leaders",
            "start_time": "2026-11-10T10:00:00Z",
            "end_time": "2026-11-10T12:00:00Z",
            "location": "Geneva Convention Center",
            "recurrence_rule": "FREQ=MONTHLY;COUNT=3",
            "attendees": [{"name": "Director General", "email": "director@sovereign.org"}],
        }
        res_create = await client.post("/api/v1/calendar/events", json=event_payload, headers=headers)
        assert res_create.status_code == 201
        event_id = res_create.json()["id"]

        # 2. Export .ics
        res_export = await client.get(f"/api/v1/calendar/events/{event_id}/export.ics", headers=headers)
        assert res_export.status_code == 200
        assert "text/calendar" in res_export.headers.get("content-type", "")
        ics_text = res_export.text
        assert "BEGIN:VCALENDAR" in ics_text
        assert "SUMMARY:Global Partner Summit" in ics_text
        assert "LOCATION:Geneva Convention Center" in ics_text
        assert "RRULE:FREQ=MONTHLY;COUNT=3" in ics_text
        assert "END:VCALENDAR" in ics_text

        # 3. Import raw .ics data
        raw_ics = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "SUMMARY:External Imported Milestone\r\n"
            "DESCRIPTION:Imported from third-party system\r\n"
            "DTSTART:20261201T080000Z\r\n"
            "DTEND:20261201T093000Z\r\n"
            "LOCATION:Room 101\r\n"
            "ATTENDEE;CN=External Guest:mailto:guest@external.com\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        res_import = await client.post(
            "/api/v1/calendar/events/import-ics",
            json={"ics_content": raw_ics},
            headers=headers,
        )
        assert res_import.status_code == 201, res_import.text
        imported_data = res_import.json()
        assert imported_data["title"] == "External Imported Milestone"
        assert imported_data["location"] == "Room 101"
        assert len(imported_data["attendees"]) == 1
        assert imported_data["attendees"][0]["email"] == "guest@external.com"


@pytest.mark.asyncio
async def test_calendar_validation_guards(db_session: AsyncSession):
    """Verify input validation guards: end_time >= start_time, and RRULE syntax."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Validation Test Co", code=f"VD_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"val_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Val Admin", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Invalid time: end_time before start_time
        invalid_time_payload = {
            "title": "Invalid Chronology",
            "start_time": "2026-10-15T12:00:00Z",
            "end_time": "2026-10-15T10:00:00Z",
        }
        res_time = await client.post("/api/v1/calendar/events", json=invalid_time_payload, headers=headers)
        assert res_time.status_code == 422

        # 2. Invalid RRULE syntax
        invalid_rrule_payload = {
            "title": "Invalid RRULE",
            "start_time": "2026-10-15T10:00:00Z",
            "end_time": "2026-10-15T11:00:00Z",
            "recurrence_rule": "INVALID_RRULE_SYNTAX_12345",
        }
        res_rrule = await client.post("/api/v1/calendar/events", json=invalid_rrule_payload, headers=headers)
        assert res_rrule.status_code == 422

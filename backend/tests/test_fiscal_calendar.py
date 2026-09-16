"""Comprehensive tests for Fiscal Calendar & Period Locking Engine."""

import uuid
import pytest
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.fiscal_calendar.service import (
    FiscalCalendarService,
    FiscalPeriodClosedException,
    FiscalPeriodNotFoundException,
)


@pytest.mark.asyncio
async def test_fiscal_year_creation_and_period_generation(db_session: AsyncSession):
    """Verify fiscal year creation, automatic generation of 12 monthly periods, and duplicate rejection."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Tenant setup
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Fiscal Test Co", code=f"FISC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"fisc_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Fiscal Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Fiscal Year 2026 with auto-generated monthly periods
        payload = {
            "name": "Fiscal Year 2026",
            "code": "FY2026",
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "auto_generate_periods": True,
            "period_type": "month",
        }
        res = await client.post("/api/v1/fiscal_calendar/years", json=payload, headers=headers)
        assert res.status_code == 201
        year_data = res.json()
        assert year_data["code"] == "FY2026"
        assert year_data["is_closed"] is False
        assert len(year_data["periods"]) == 12

        # Verify monthly period sequence
        first_period = year_data["periods"][0]
        assert first_period["code"] == "2026-01"
        assert first_period["date_from"] == "2026-01-01"
        assert first_period["date_to"] == "2026-01-31"
        assert first_period["state"] == "open"

        last_period = year_data["periods"][-1]
        assert last_period["code"] == "2026-12"
        assert last_period["date_from"] == "2026-12-01"
        assert last_period["date_to"] == "2026-12-31"

        # 2. Duplicate rejection
        dup_res = await client.post("/api/v1/fiscal_calendar/years", json=payload, headers=headers)
        assert dup_res.status_code == 409

        # 3. List years
        list_res = await client.get("/api/v1/fiscal_calendar/years", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_date_validation_and_period_locking(db_session: AsyncSession):
    """Verify transaction posting date validation, period locking, and backdating protection."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Locking Test Co", code=f"LOCK_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"lock_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Lock Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create Year
        year_res = await client.post(
            "/api/v1/fiscal_calendar/years",
            json={"name": "FY 2026", "code": "FY2026", "date_from": "2026-01-01", "date_to": "2026-12-31", "auto_generate_periods": True},
            headers=headers,
        )
        periods = year_res.json()["periods"]
        p_jan = next(p for p in periods if p["code"] == "2026-01")

        # 1. Validate open date in January
        val_open = await client.post(
            "/api/v1/fiscal_calendar/validate-date",
            json={"target_date": "2026-01-15"},
            headers=headers,
        )
        assert val_open.status_code == 200
        assert val_open.json()["is_open"] is True
        assert val_open.json()["period_code"] == "2026-01"

        # Direct domain assert should succeed
        assert_period = await FiscalCalendarService.assert_period_open(db_session, comp_id, date(2026, 1, 15))
        assert assert_period.code == "2026-01"

        # 2. Lock January period
        lock_res = await client.post(f"/api/v1/fiscal_calendar/periods/{p_jan['id']}/lock", headers=headers)
        assert lock_res.status_code == 200
        assert lock_res.json()["state"] == "locked"

        # 3. Validate locked date -> now is_open=False
        val_locked = await client.post(
            "/api/v1/fiscal_calendar/validate-date",
            json={"target_date": "2026-01-15"},
            headers=headers,
        )
        assert val_locked.status_code == 200
        assert val_locked.json()["is_open"] is False
        assert val_locked.json()["period_state"] == "locked"

        # Direct domain assert must raise FiscalPeriodClosedException
        with pytest.raises(FiscalPeriodClosedException):
            await FiscalCalendarService.assert_period_open(db_session, comp_id, date(2026, 1, 15))

        # 4. Reopen January period
        reopen_res = await client.post(f"/api/v1/fiscal_calendar/periods/{p_jan['id']}/reopen", headers=headers)
        assert reopen_res.status_code == 200
        assert reopen_res.json()["state"] == "open"

        # Assert open again
        reopened = await FiscalCalendarService.assert_period_open(db_session, comp_id, date(2026, 1, 15))
        assert reopened.state == "open"


@pytest.mark.asyncio
async def test_fiscal_year_closing_cascades_lock(db_session: AsyncSession):
    """Verify closing a fiscal year locks all periods and blocks reopening."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Year Close Co", code=f"CLS_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"close_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Close Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create Year
        year_res = await client.post(
            "/api/v1/fiscal_calendar/years",
            json={"name": "FY 2025", "code": "FY2025", "date_from": "2025-01-01", "date_to": "2025-12-31", "auto_generate_periods": True},
            headers=headers,
        )
        year_id = year_res.json()["id"]
        p_id = year_res.json()["periods"][0]["id"]

        # Close Year
        close_res = await client.post(f"/api/v1/fiscal_calendar/years/{year_id}/close", headers=headers)
        assert close_res.status_code == 200
        assert close_res.json()["is_closed"] is True

        # Check all periods are locked
        periods_res = await client.get(f"/api/v1/fiscal_calendar/periods?year_id={year_id}", headers=headers)
        assert all(p["state"] == "locked" for p in periods_res.json())

        # Attempting to reopen a period in a closed year must fail
        reopen_res = await client.post(f"/api/v1/fiscal_calendar/periods/{p_id}/reopen", headers=headers)
        assert reopen_res.status_code == 400


@pytest.mark.asyncio
async def test_date_out_of_bounds(db_session: AsyncSession):
    """Verify validation when date has no fiscal calendar defined."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Bounds Co", code=f"BND_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"bounds_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Bounds Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Validate date with no periods
        val_res = await client.post(
            "/api/v1/fiscal_calendar/validate-date",
            json={"target_date": "2099-01-01"},
            headers=headers,
        )
        assert val_res.status_code == 200
        assert val_res.json()["is_open"] is False

        # Domain assert raises FiscalPeriodNotFoundException
        with pytest.raises(FiscalPeriodNotFoundException):
            await FiscalCalendarService.assert_period_open(db_session, comp_id, date(2099, 1, 1))

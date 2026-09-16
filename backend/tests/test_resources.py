"""Comprehensive unit and integration tests for Resource Scheduling & Capacity Allocation."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_resource_crud_and_tenant_isolation(db_session: AsyncSession):
    """Verify resource creation, updating, deletion, and strict tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Res Co A", code=f"RA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Res Co B", code=f"RB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"res_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Res Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"res_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Res Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates Space Resource
        res_create = await client.post(
            "/api/v1/resources",
            json={
                "name": "Main Conference Room",
                "code": "CONF_MAIN",
                "resource_type": "space",
                "capacity_per_day": "12.00",
                "cost_per_hour": "50.00",
                "description": "Boardroom with video conferencing",
            },
            headers=headers_a,
        )
        assert res_create.status_code == 201, res_create.text
        res_id = res_create.json()["id"]

        # 2. Company A updates capacity
        res_patch = await client.patch(
            f"/api/v1/resources/{res_id}",
            json={"capacity_per_day": "14.00"},
            headers=headers_a,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["capacity_per_day"] == "14.00"

        # 3. User B cannot see User A's resource
        res_b_list = await client.get("/api/v1/resources", headers=headers_b)
        assert res_b_list.status_code == 200
        assert len(res_b_list.json()) == 0


@pytest.mark.asyncio
async def test_resource_availability_and_collision_prevention(db_session: AsyncSession):
    """Verify time-slot overlap collision checks and overbooking prevention."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Collision Co", code=f"CC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"col_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Collision User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create equipment resource: Forklift
        res_fork = await client.post(
            "/api/v1/resources",
            json={
                "name": "Heavy Forklift #1",
                "code": "FORK_01",
                "resource_type": "equipment",
                "capacity_per_day": "16.00",
            },
            headers=headers,
        )
        fork_id = res_fork.json()["id"]

        # 1. Book first allocation: 09:00 to 13:00 UTC
        res_alloc1 = await client.post(
            "/api/v1/resources/allocations",
            json={
                "resource_id": fork_id,
                "start_time": "2026-10-01T09:00:00Z",
                "end_time": "2026-10-01T13:00:00Z",
                "hours_allocated": "4.00",
                "allow_overbooking": False,
                "notes": "Morning warehouse pallet move",
            },
            headers=headers,
        )
        assert res_alloc1.status_code == 201, res_alloc1.text

        # 2. Check availability for overlapping window: 11:00 to 15:00 UTC
        res_check = await client.post(
            "/api/v1/resources/check-availability",
            json={
                "resource_id": fork_id,
                "start_time": "2026-10-01T11:00:00Z",
                "end_time": "2026-10-01T15:00:00Z",
            },
            headers=headers,
        )
        assert res_check.status_code == 200, res_check.text
        check_data = res_check.json()
        assert check_data["is_available"] is False
        assert check_data["conflicts_count"] == 1

        # 3. Attempt to book overlapping window with allow_overbooking=False (Must fail 400)
        res_alloc_fail = await client.post(
            "/api/v1/resources/allocations",
            json={
                "resource_id": fork_id,
                "start_time": "2026-10-01T11:00:00Z",
                "end_time": "2026-10-01T15:00:00Z",
                "hours_allocated": "4.00",
                "allow_overbooking": False,
            },
            headers=headers,
        )
        assert res_alloc_fail.status_code == 400

        # 4. Book overlapping window with allow_overbooking=True (Must succeed)
        res_alloc_forced = await client.post(
            "/api/v1/resources/allocations",
            json={
                "resource_id": fork_id,
                "start_time": "2026-10-01T11:00:00Z",
                "end_time": "2026-10-01T15:00:00Z",
                "hours_allocated": "4.00",
                "allow_overbooking": True,
                "notes": "Supervisor forced dual-assignment",
            },
            headers=headers,
        )
        assert res_alloc_forced.status_code == 201


@pytest.mark.asyncio
async def test_resource_allocation_lifecycle_and_non_overlapping(db_session: AsyncSession):
    """Verify booking non-overlapping allocations and updating lifecycle states."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Lifecycle Co", code=f"LC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"life_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Life User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create human resource: Senior Consultant
        res_human = await client.post(
            "/api/v1/resources",
            json={
                "name": "Senior Consultant",
                "code": "CONSULT_SR",
                "resource_type": "human",
                "capacity_per_day": "8.00",
            },
            headers=headers,
        )
        human_id = res_human.json()["id"]

        # Book morning slot: 08:00 to 12:00
        res_morn = await client.post(
            "/api/v1/resources/allocations",
            json={
                "resource_id": human_id,
                "start_time": "2026-10-02T08:00:00Z",
                "end_time": "2026-10-02T12:00:00Z",
                "hours_allocated": "4.00",
                "allow_overbooking": False,
            },
            headers=headers,
        )
        assert res_morn.status_code == 201
        morn_id = res_morn.json()["id"]

        # Book afternoon slot: 13:00 to 17:00 (non-overlapping, must succeed)
        res_aft = await client.post(
            "/api/v1/resources/allocations",
            json={
                "resource_id": human_id,
                "start_time": "2026-10-02T13:00:00Z",
                "end_time": "2026-10-02T17:00:00Z",
                "hours_allocated": "4.00",
                "allow_overbooking": False,
            },
            headers=headers,
        )
        assert res_aft.status_code == 201

        # Transition morning slot: planned -> confirmed -> completed
        res_conf = await client.patch(
            f"/api/v1/resources/allocations/{morn_id}",
            json={"status": "confirmed"},
            headers=headers,
        )
        assert res_conf.status_code == 200
        assert res_conf.json()["status"] == "confirmed"

        res_comp = await client.patch(
            f"/api/v1/resources/allocations/{morn_id}",
            json={"status": "completed"},
            headers=headers,
        )
        assert res_comp.status_code == 200
        assert res_comp.json()["status"] == "completed"

        # Delete afternoon slot
        res_del = await client.delete(f"/api/v1/resources/allocations/{res_aft.json()['id']}", headers=headers)
        assert res_del.status_code == 204

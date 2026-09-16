"""Automated unit test suite for the Universal Sequence & Legal Auto-Numbering Engine."""

import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.sequences.models import Sequence
from modules.base.sequences.service import SequenceService


@pytest.mark.asyncio
async def test_sequence_crud_and_validation(db_session: AsyncSession):
    """Verify sequence registration, reading, updating, and soft-deletion via REST API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup tenant & user
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Sequence Test Co", code=f"SEQ_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"seq_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Seq Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create custom sequence
        create_payload = {
            "name": "Custom Ticket Numbering",
            "code": "helpdesk.ticket",
            "prefix": "TICK-%(year)s-",
            "suffix": "",
            "padding": 4,
            "current_number": 100,
            "step": 1,
            "reset_period": "never",
            "is_active": True,
        }
        res = await client.post("/api/v1/sequences/", json=create_payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        seq_id = data["id"]
        assert data["code"] == "helpdesk.ticket"
        assert data["current_number"] == 100

        # Duplicate code rejection
        dup_res = await client.post("/api/v1/sequences/", json=create_payload, headers=headers)
        assert dup_res.status_code == 409

        # 2. Get Sequence
        get_res = await client.get(f"/api/v1/sequences/{seq_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Custom Ticket Numbering"

        # 3. List Sequences with search
        list_res = await client.get("/api/v1/sequences/?search=ticket", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # 4. Update Sequence
        patch_payload = {"padding": 6, "name": "Enhanced Ticket Numbering"}
        patch_res = await client.patch(f"/api/v1/sequences/{seq_id}", json=patch_payload, headers=headers)
        assert patch_res.status_code == 200
        assert patch_res.json()["padding"] == 6
        assert patch_res.json()["name"] == "Enhanced Ticket Numbering"

        # 5. Soft-delete Sequence
        del_res = await client.delete(f"/api/v1/sequences/{seq_id}", headers=headers)
        assert del_res.status_code == 204

        # Verify not in list
        list_res2 = await client.get("/api/v1/sequences/", headers=headers)
        assert not any(s["id"] == seq_id for s in list_res2.json())


@pytest.mark.asyncio
async def test_sequence_seeding_and_atomic_allocation(db_session: AsyncSession):
    """Verify standard fixtures seeding, atomic allocation, date tokens, and gapless numbers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Invoice Seq Co", code=f"INV_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"inv_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Inv Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Bootstrap standard sequences
        seed_res = await client.post("/api/v1/sequences/seed", headers=headers)
        assert seed_res.status_code == 200
        assert seed_res.json()["seeded_sequences"] >= 6

        # 2. Allocate consecutive invoice numbers
        # Next 1
        alloc1 = await client.post("/api/v1/sequences/account.invoice/next", json={}, headers=headers)
        assert alloc1.status_code == 200
        data1 = alloc1.json()
        assert data1["number"] == 1
        current_year = datetime.now(timezone.utc).strftime("%Y")
        current_month = datetime.now(timezone.utc).strftime("%m")
        expected_seq1 = f"INV/{current_year}/{current_month}/00001"
        assert data1["sequence_number"] == expected_seq1

        # Next 2
        alloc2 = await client.post("/api/v1/sequences/account.invoice/next", json={}, headers=headers)
        assert alloc2.status_code == 200
        data2 = alloc2.json()
        assert data2["number"] == 2
        assert data2["sequence_number"] == f"INV/{current_year}/{current_month}/00002"

        # Next 3 (Gapless consecutive increment)
        alloc3 = await client.post("/api/v1/sequences/account.invoice/next", json={}, headers=headers)
        assert alloc3.status_code == 200
        assert alloc3.json()["number"] == 3


@pytest.mark.asyncio
async def test_sequence_peek_non_mutating(db_session: AsyncSession):
    """Verify peek endpoint returns the preview string without advancing the database counter."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Peek Test Co", code=f"PEEK_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"peek_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Peek Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Seed fixtures
        await client.post("/api/v1/sequences/seed", headers=headers)

        # 1. Peek next sales order
        peek1 = await client.get("/api/v1/sequences/sale.order/peek", headers=headers)
        assert peek1.status_code == 200
        data_peek1 = peek1.json()
        assert data_peek1["number"] == 1
        assert data_peek1["is_preview"] is True

        # 2. Peek again - counter must NOT have changed!
        peek2 = await client.get("/api/v1/sequences/sale.order/peek", headers=headers)
        assert peek2.status_code == 200
        assert peek2.json()["number"] == 1

        # 3. Now allocate
        alloc = await client.post("/api/v1/sequences/sale.order/next", json={}, headers=headers)
        assert alloc.json()["number"] == 1

        # 4. Peek again - now previews number 2
        peek3 = await client.get("/api/v1/sequences/sale.order/peek", headers=headers)
        assert peek3.json()["number"] == 2


@pytest.mark.asyncio
async def test_sequence_periodic_reset_and_tenant_isolation(db_session: AsyncSession):
    """Verify yearly reset behavior across context dates and strict multi-company boundary isolation."""
    # 1. Company A setup
    comp_a = uuid.uuid4()
    comp_b = uuid.uuid4()
    db_session.add(Company(id=comp_a, name="Company Alpha", code=f"ALPH_{comp_a.hex[:4]}"))
    db_session.add(Company(id=comp_b, name="Company Beta", code=f"BETA_{comp_b.hex[:4]}"))
    await db_session.commit()

    seq_a = Sequence(
        company_id=comp_a,
        name="Contract A",
        code="contract.yearly",
        prefix="CON/%(year)s/",
        padding=4,
        current_number=0,
        step=1,
        reset_period="yearly",
        is_active=True,
    )
    seq_b = Sequence(
        company_id=comp_b,
        name="Contract B",
        code="contract.yearly",
        prefix="CON/%(year)s/",
        padding=4,
        current_number=0,
        step=1,
        reset_period="yearly",
        is_active=True,
    )
    db_session.add_all([seq_a, seq_b])
    await db_session.commit()

    # Allocate in 2026 for Company A
    d_2026 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    num1_a, count1_a = await SequenceService.get_next_number(db_session, comp_a, "contract.yearly", d_2026)
    assert num1_a == "CON/2026/0001"
    assert count1_a == 1

    num2_a, count2_a = await SequenceService.get_next_number(db_session, comp_a, "contract.yearly", d_2026)
    assert num2_a == "CON/2026/0002"
    assert count2_a == 2

    # Tenant Isolation: Company B's counter must still be untouched!
    num1_b, count1_b = await SequenceService.get_next_number(db_session, comp_b, "contract.yearly", d_2026)
    assert num1_b == "CON/2026/0001"
    assert count1_b == 1

    # Yearly Reset: Allocate for Company A in 2027
    d_2027 = datetime(2027, 1, 10, 8, 30, 0, tzinfo=timezone.utc)
    num_reset_a, count_reset_a = await SequenceService.get_next_number(db_session, comp_a, "contract.yearly", d_2027)
    assert num_reset_a == "CON/2027/0001"
    assert count_reset_a == 1

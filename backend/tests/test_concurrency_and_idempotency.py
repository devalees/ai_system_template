"""Comprehensive tests for Optimistic Concurrency Control (OCC) and Idempotency Shield."""

import uuid
import pytest
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from main import app
from core.database import AsyncSessionLocal
from core.concurrency import assert_version_match, ConcurrencyConflictException
from modules.base.identity_rbac.models import Company, User
from modules.base.sequences.models import Sequence
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_occ_version_increment_and_stale_detection(db_session: AsyncSession):
    """Verify that version_id starts at 1, increments on update, and detects stale lost updates."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="OCC Test Co", code=f"OCC_{comp_id.hex[:4]}")
    db_session.add(company)
    await db_session.commit()

    # Verify initial version_id is 1
    assert company.version_id == 1

    # Update company in current session
    company.name = "OCC Test Co Updated"
    await db_session.commit()
    assert company.version_id == 2

    # Open two separate sessions to simulate concurrent workers
    async with AsyncSessionLocal() as session_a, AsyncSessionLocal() as session_b:
        # Both sessions load the same company with version_id = 2
        comp_a = (await session_a.execute(select(Company).where(Company.id == comp_id))).scalar_one()
        comp_b = (await session_b.execute(select(Company).where(Company.id == comp_id))).scalar_one()

        assert comp_a.version_id == 2
        assert comp_b.version_id == 2

        # Session A updates first and commits
        comp_a.name = "Updated by Worker A"
        await session_a.commit()
        assert comp_a.version_id == 3

        # Session B attempts to update the stale record
        comp_b.name = "Conflicting Update by Worker B"
        with pytest.raises(StaleDataError):
            await session_b.commit()


@pytest.mark.asyncio
async def test_assert_version_match_helper():
    """Verify assert_version_match utility validates matching versions and rejects stale ones."""
    class FakeEntity:
        def __init__(self, version: int):
            self.version_id = version

    entity = FakeEntity(version=3)

    # Matching version or None passes silently
    assert_version_match(entity, None)
    assert_version_match(entity, 3)

    # Mismatched version raises ConcurrencyConflictException
    with pytest.raises(ConcurrencyConflictException) as exc_info:
        assert_version_match(entity, expected_version=2, resource_name="TestOrder")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "CONCURRENCY_CONFLICT"
    assert exc_info.value.details["current_version"] == 3
    assert exc_info.value.details["expected_version"] == 2


@pytest.mark.asyncio
async def test_idempotency_shield_caching_and_hit(db_session: AsyncSession):
    """Verify that repeating a mutating POST request with Idempotency-Key returns cached response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup tenant
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Idempotency Co", code=f"IDEM_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"idem_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Idem Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        token = login_res.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Company-ID": str(comp_id),
            "Idempotency-Key": f"key_{uuid.uuid4().hex}",
        }

        create_payload = {
            "name": "Purchase Requisition Numbering",
            "code": f"req.number_{uuid.uuid4().hex[:4]}",
            "prefix": "REQ-",
            "padding": 4,
            "current_number": 1,
            "step": 1,
            "reset_period": "never",
        }

        # 1. Initial execution -> X-Idempotency-Status: STORED
        res1 = await client.post("/api/v1/sequences/", json=create_payload, headers=headers)
        assert res1.status_code == 201
        assert res1.headers.get("X-Idempotency-Status") == "STORED"
        data1 = res1.json()
        seq_id = data1["id"]

        # 2. Second request with identical Idempotency-Key -> X-Idempotency-Status: HIT
        res2 = await client.post("/api/v1/sequences/", json=create_payload, headers=headers)
        assert res2.status_code == 201
        assert res2.headers.get("X-Idempotency-Status") == "HIT"
        data2 = res2.json()
        # Exactly identical response payload
        assert data2["id"] == seq_id
        assert data2["code"] == create_payload["code"]

        # 3. Third request without Idempotency-Key -> fails with 409 duplicate sequence code
        headers_no_idem = {"Authorization": f"Bearer {token}", "X-Company-ID": str(comp_id)}
        res3 = await client.post("/api/v1/sequences/", json=create_payload, headers=headers_no_idem)
        assert res3.status_code == 409  # Duplicate code rejected by domain logic


@pytest.mark.asyncio
async def test_idempotency_tenant_isolation(db_session: AsyncSession):
    """Verify that identical Idempotency-Keys in different tenant companies do not collide."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup Company A
        comp_a = Company(id=uuid.uuid4(), name="Company A", code=f"COA_{uuid.uuid4().hex[:4]}")
        db_session.add(comp_a)
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a.id, {"allow_registration": True})

        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "User A", "company_id": str(comp_a.id)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        token_a = login_a.json()["access_token"]

        # Setup Company B
        comp_b = Company(id=uuid.uuid4(), name="Company B", code=f"COB_{uuid.uuid4().hex[:4]}")
        db_session.add(comp_b)
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b.id, {"allow_registration": True})

        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "User B", "company_id": str(comp_b.id)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        token_b = login_b.json()["access_token"]

        # Shared idempotency key
        shared_key = f"shared_idem_key_{uuid.uuid4().hex}"

        # Tenant A request
        res_a = await client.post(
            "/api/v1/sequences/",
            json={"name": "Seq A", "code": "seq.alpha", "prefix": "A-", "padding": 4, "current_number": 1, "step": 1, "reset_period": "never"},
            headers={"Authorization": f"Bearer {token_a}", "X-Company-ID": str(comp_a.id), "Idempotency-Key": shared_key},
        )
        assert res_a.status_code == 201
        assert res_a.headers.get("X-Idempotency-Status") == "STORED"
        assert res_a.json()["company_id"] == str(comp_a.id)

        # Tenant B request with the same idempotency key executes independently (STORED, not HIT)
        res_b = await client.post(
            "/api/v1/sequences/",
            json={"name": "Seq B", "code": "seq.alpha", "prefix": "B-", "padding": 4, "current_number": 1, "step": 1, "reset_period": "never"},
            headers={"Authorization": f"Bearer {token_b}", "X-Company-ID": str(comp_b.id), "Idempotency-Key": shared_key},
        )
        assert res_b.status_code == 201
        assert res_b.headers.get("X-Idempotency-Status") == "STORED"
        assert res_b.json()["company_id"] == str(comp_b.id)

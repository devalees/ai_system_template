"""Automated test suite for Audit Trail & Diff Engine."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.audit.models import AuditLog
from modules.base.audit.service import AuditService, compute_instance_diff
from modules.base.identity_rbac.models import User, Company


@pytest.mark.asyncio
async def test_audit_service_mutation_and_trail(db_session: AsyncSession):
    """Test manual and automated audit logging of record lifecycle events."""
    company_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    record_id = uuid.uuid4()

    # 1. Log CREATE event
    create_log = await AuditService.log_mutation(
        db=db_session,
        model_name="Product",
        record_id=record_id,
        action="CREATE",
        changes={"name": {"old": None, "new": "Sovereign Laptop"}, "price": {"old": None, "new": 1200.0}},
        company_id=company_id,
        actor_id=actor_id,
        actor_type="human",
    )
    assert create_log.id is not None
    assert create_log.action == "CREATE"
    assert create_log.changes["name"]["new"] == "Sovereign Laptop"

    # 2. Log UPDATE event
    update_log = await AuditService.log_mutation(
        db=db_session,
        model_name="Product",
        record_id=record_id,
        action="UPDATE",
        changes={"price": {"old": 1200.0, "new": 1050.0}},
        company_id=company_id,
        actor_id=actor_id,
        actor_type="ai_agent",
    )
    assert update_log.action == "UPDATE"
    assert update_log.actor_type == "ai_agent"

    # 3. Retrieve trail
    trail = await AuditService.get_record_trail(
        db=db_session,
        model_name="Product",
        record_id=record_id,
        company_id=company_id,
    )
    assert len(trail) == 2
    assert trail[0].action == "CREATE"
    assert trail[1].action == "UPDATE"


@pytest.mark.asyncio
async def test_compute_instance_diff(db_session: AsyncSession):
    """Verify compute_instance_diff correctly detects attribute mutations."""
    user = User(
        email=f"diff_{uuid.uuid4().hex[:6]}@example.com",
        username=f"diff_{uuid.uuid4().hex[:6]}",
        hashed_password="secret_hash",
        full_name="Original Name",
        company_id=uuid.uuid4(),
    )
    db_session.add(user)
    await db_session.flush()

    # Mutate attribute
    user.full_name = "Updated Name"
    diff = compute_instance_diff(user)
    assert "full_name" in diff
    assert diff["full_name"]["old"] == "Original Name"
    assert diff["full_name"]["new"] == "Updated Name"
    # Verify sensitive attributes like password are not included
    assert "hashed_password" not in diff


@pytest.mark.asyncio
async def test_audit_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify HTTP audit endpoints and cross-tenant audit isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}"),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}"),
        ])
        await db_session.commit()

        from modules.base.settings.service import SettingsService
        await SettingsService.update_settings(db_session, "identity_rbac", company_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", company_b, {"allow_registration": True})

        # 1. Register Tenant A
        user_a = f"audit_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@test.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Tenant A Auditor",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # 2. Register Tenant B
        user_b = f"audit_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@test.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Tenant B Auditor",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 3. Create audit entry for Tenant A
        rec_id = uuid.uuid4()
        await AuditService.log_mutation(
            db=db_session,
            model_name="Invoice",
            record_id=rec_id,
            action="CREATE",
            changes={"total": {"old": None, "new": 500}},
            company_id=company_a,
        )

        # 4. Tenant A accesses audit log
        res_a = await client.get("/api/v1/audit/", headers=headers_a)
        assert res_a.status_code == 200
        logs_a = res_a.json()
        assert len(logs_a) >= 1
        assert any(l["record_id"] == str(rec_id) for l in logs_a)

        # 5. Tenant A accesses entity specific trail
        res_trail_a = await client.get(f"/api/v1/audit/entity/Invoice/{rec_id}", headers=headers_a)
        assert res_trail_a.status_code == 200
        trail_a = res_trail_a.json()
        assert len(trail_a) == 1
        assert trail_a[0]["action"] == "CREATE"

        # 6. Tenant B accesses audit log -> must be empty / not include Tenant A's entries
        res_b = await client.get("/api/v1/audit/", headers=headers_b)
        assert res_b.status_code == 200
        logs_b = res_b.json()
        assert not any(l["record_id"] == str(rec_id) for l in logs_b)

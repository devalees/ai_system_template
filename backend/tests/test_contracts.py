"""Comprehensive unit and integration tests for Contracts, Agreements & Subscriptions."""

import uuid
import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.parties.models import Party
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_contract_crud_and_tenant_isolation(db_session: AsyncSession):
    """Verify contract creation, line item calculation, and tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Contract Co A", code=f"CA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Contract Co B", code=f"CB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"ctr_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Contract Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"ctr_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Contract Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # Create Party in Company A
        party_a = Party(company_id=comp_a, name="ACME Enterprises", is_customer=True)
        db_session.add(party_a)
        await db_session.commit()
        await db_session.refresh(party_a)

        # 1. Company A creates Contract
        res_create = await client.post(
            "/api/v1/contracts",
            json={
                "title": "Master Services Agreement 2026",
                "party_id": str(party_a.id),
                "contract_type": "customer",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "billing_frequency": "monthly",
                "amount": "60000.00",
                "auto_renew": True,
                "notice_days": 30,
                "lines": [
                    {
                        "name": "Cloud Platform Retainer",
                        "quantity": "12.0000",
                        "unit_price": "5000.0000",
                    }
                ],
            },
            headers=headers_a,
        )
        assert res_create.status_code == 201, res_create.text
        ctr_data = res_create.json()
        assert ctr_data["title"] == "Master Services Agreement 2026"
        assert ctr_data["party_name"] == "ACME Enterprises"
        assert ctr_data["state"] == "draft"
        assert len(ctr_data["lines"]) == 1
        assert ctr_data["lines"][0]["subtotal"] == "60000.00"

        # 2. User B cannot see User A's contracts
        res_b_list = await client.get("/api/v1/contracts", headers=headers_b)
        assert res_b_list.status_code == 200
        assert len(res_b_list.json()) == 0


@pytest.mark.asyncio
async def test_contract_lifecycle_transitions(db_session: AsyncSession):
    """Verify Draft -> Active -> Renew -> Terminate lifecycle flow."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Life Contract Co", code=f"LC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"life_ctr_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Life Ctr User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        party = Party(company_id=comp_id, name="Software Partner LLC", is_vendor=True)
        db_session.add(party)
        await db_session.commit()
        await db_session.refresh(party)

        # 1. Create Draft Contract
        res_c = await client.post(
            "/api/v1/contracts",
            json={
                "title": "Vendor Support Subscription",
                "party_id": str(party.id),
                "contract_type": "vendor",
                "start_date": "2026-03-01",
                "end_date": "2026-08-31",
                "amount": "15000.00",
            },
            headers=headers,
        )
        assert res_c.status_code == 201
        ctr_id = res_c.json()["id"]
        assert res_c.json()["state"] == "draft"

        # 2. Activate Contract
        res_act = await client.post(f"/api/v1/contracts/{ctr_id}/activate", headers=headers)
        assert res_act.status_code == 200
        assert res_act.json()["state"] == "active"

        # 3. Renew Contract to new end date
        res_renew = await client.post(
            f"/api/v1/contracts/{ctr_id}/renew",
            json={"new_end_date": "2027-02-28"},
            headers=headers,
        )
        assert res_renew.status_code == 200
        assert res_renew.json()["end_date"] == "2027-02-28"
        assert res_renew.json()["state"] == "active"

        # 4. Terminate Contract
        res_term = await client.post(
            f"/api/v1/contracts/{ctr_id}/terminate",
            json={"reason": "Mutual agreement to migrate to Enterprise tier"},
            headers=headers,
        )
        assert res_term.status_code == 200
        assert res_term.json()["state"] == "terminated"

        # 5. Cannot activate terminated contract (must fail 400)
        res_fail = await client.post(f"/api/v1/contracts/{ctr_id}/activate", headers=headers)
        assert res_fail.status_code == 400


@pytest.mark.asyncio
async def test_expiring_contracts_detection(db_session: AsyncSession):
    """Verify detection of active contracts nearing expiry within specified horizon."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Expiry Co", code=f"EX_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"exp_u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Exp User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        party = Party(company_id=comp_id, name="Leasehold Corp", is_customer=True)
        db_session.add(party)
        await db_session.commit()
        await db_session.refresh(party)

        today = date.today()

        # Contract 1: Ends in 10 days, ACTIVE -> MUST BE IN EXPIRING LIST
        res_c1 = await client.post(
            "/api/v1/contracts",
            json={
                "title": "Office Space Lease - Expiring Soon",
                "party_id": str(party.id),
                "contract_type": "lease",
                "start_date": str(today - timedelta(days=350)),
                "end_date": str(today + timedelta(days=10)),
                "amount": "24000.00",
            },
            headers=headers,
        )
        c1_id = res_c1.json()["id"]
        await client.post(f"/api/v1/contracts/{c1_id}/activate", headers=headers)

        # Contract 2: Ends in 90 days, ACTIVE -> NOT in 30-day horizon
        res_c2 = await client.post(
            "/api/v1/contracts",
            json={
                "title": "Office Space Lease - Long Term",
                "party_id": str(party.id),
                "contract_type": "lease",
                "start_date": str(today),
                "end_date": str(today + timedelta(days=90)),
                "amount": "50000.00",
            },
            headers=headers,
        )
        c2_id = res_c2.json()["id"]
        await client.post(f"/api/v1/contracts/{c2_id}/activate", headers=headers)

        # Contract 3: Ends in 10 days, but DRAFT -> NOT counted
        await client.post(
            "/api/v1/contracts",
            json={
                "title": "Draft Contract",
                "party_id": str(party.id),
                "start_date": str(today),
                "end_date": str(today + timedelta(days=10)),
                "amount": "1000.00",
            },
            headers=headers,
        )

        # Query expiring within 30 days
        res_exp = await client.get("/api/v1/contracts/expiring?horizon_days=30", headers=headers)
        assert res_exp.status_code == 200, res_exp.text
        exp_list = res_exp.json()
        assert len(exp_list) == 1
        assert exp_list[0]["id"] == c1_id
        assert exp_list[0]["title"] == "Office Space Lease - Expiring Soon"

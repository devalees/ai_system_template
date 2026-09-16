"""Comprehensive tests for Universal Party & Contact Engine."""

import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.lookups.models import Currency


@pytest.mark.asyncio
async def test_party_dual_role_creation_and_contacts(db_session: AsyncSession):
    """Verify unified party creation with dual customer/vendor roles, credit limit, and child contacts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Party Test Co", code=f"PTY_{comp_id.hex[:4]}"))

        curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        db_session.add(curr)
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"pty_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Party Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Dual Customer & Vendor Party
        create_payload = {
            "name": "OmniCorp Logistics",
            "legal_name": "OmniCorp Logistics International S.A.E.",
            "is_company": True,
            "is_customer": True,
            "is_vendor": True,
            "tax_id": "EG-TAX-1029384",
            "commercial_reg_no": "CR-887766",
            "currency_id": str(curr.id),
            "credit_limit": 100000.00,
            "email": "contact@omnicorp.com",
            "website": "https://www.omnicorp.com",
            "contacts": [
                {
                    "name": "Hesham Raafat",
                    "job_title": "Commercial Director",
                    "email": "hesham@omnicorp.com",
                    "is_primary": True,
                }
            ],
        }

        res = await client.post("/api/v1/parties/", json=create_payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "OmniCorp Logistics"
        assert data["is_customer"] is True
        assert data["is_vendor"] is True
        assert data["currency_code"] == "USD"
        assert Decimal(data["credit_limit"]) == Decimal("100000.00")
        assert len(data["contacts"]) == 1
        assert data["contacts"][0]["name"] == "Hesham Raafat"
        assert data["contacts"][0]["is_primary"] is True

        # 2. Filter query by is_customer=True
        cust_res = await client.get("/api/v1/parties/?is_customer=true", headers=headers)
        assert cust_res.status_code == 200
        assert any(p["id"] == data["id"] for p in cust_res.json())

        # 3. Filter query by is_vendor=True
        vend_res = await client.get("/api/v1/parties/?is_vendor=true", headers=headers)
        assert vend_res.status_code == 200
        assert any(p["id"] == data["id"] for p in vend_res.json())


@pytest.mark.asyncio
async def test_corporate_hierarchy_and_circular_protection(db_session: AsyncSession):
    """Verify recursive corporate holding tree generation and circular parent assignment prevention."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Holding Co", code=f"HLD_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"hld_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Holding Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Parent Holding Company A
        res_a = await client.post("/api/v1/parties/", json={"name": "Global Holding Corp", "is_company": True}, headers=headers)
        party_a_id = res_a.json()["id"]

        # 2. Create Subsidiary B with parent_id = A
        res_b = await client.post("/api/v1/parties/", json={"name": "Middle East Subsidiary", "parent_id": party_a_id}, headers=headers)
        party_b_id = res_b.json()["id"]

        # 3. Create Branch C with parent_id = B
        res_c = await client.post("/api/v1/parties/", json={"name": "Cairo Branch", "parent_id": party_b_id}, headers=headers)
        party_c_id = res_c.json()["id"]

        # 4. Fetch Hierarchy tree from Root A
        tree_res = await client.get(f"/api/v1/parties/{party_a_id}/hierarchy", headers=headers)
        assert tree_res.status_code == 200
        tree = tree_res.json()
        assert tree["id"] == party_a_id
        assert tree["name"] == "Global Holding Corp"
        assert len(tree["subsidiaries"]) == 1
        assert tree["subsidiaries"][0]["id"] == party_b_id
        assert tree["subsidiaries"][0]["subsidiaries"][0]["id"] == party_c_id

        # 5. Prevent Self-Parenting (A.parent_id = A.id)
        self_res = await client.patch(f"/api/v1/parties/{party_a_id}", json={"parent_id": party_a_id}, headers=headers)
        assert self_res.status_code == 400
        assert self_res.json()["error"]["code"] == "SELF_PARENT_NOT_ALLOWED"

        # 6. Prevent Circular Assignment (Setting A.parent_id = C.id would create A -> B -> C -> A)
        cycle_res = await client.patch(f"/api/v1/parties/{party_a_id}", json={"parent_id": party_c_id}, headers=headers)
        assert cycle_res.status_code == 400
        assert cycle_res.json()["error"]["code"] == "CYCLIC_HIERARCHY_DETECTED"


@pytest.mark.asyncio
async def test_contacts_single_primary_enforcement(db_session: AsyncSession):
    """Verify child contacts management and single-primary contact enforcement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Contacts Co", code=f"CTC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"ctc_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Contact Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create Party
        party_res = await client.post("/api/v1/parties/", json={"name": "Alpha Traders"}, headers=headers)
        party_id = party_res.json()["id"]

        # 1. Add Contact 1 as primary
        c1_res = await client.post(
            f"/api/v1/parties/{party_id}/contacts",
            json={"name": "Alice Smith", "is_primary": True, "email": "alice@alpha.com"},
            headers=headers,
        )
        assert c1_res.status_code == 201
        c1_id = c1_res.json()["id"]
        assert c1_res.json()["is_primary"] is True

        # 2. Add Contact 2 as primary -> Contact 1 must lose primary status
        c2_res = await client.post(
            f"/api/v1/parties/{party_id}/contacts",
            json={"name": "Bob Jones", "is_primary": True, "email": "bob@alpha.com"},
            headers=headers,
        )
        assert c2_res.status_code == 201
        c2_id = c2_res.json()["id"]
        assert c2_res.json()["is_primary"] is True

        # 3. Verify Contact 1 is now is_primary = False
        contacts_list = (await client.get(f"/api/v1/parties/{party_id}/contacts", headers=headers)).json()
        c1_updated = next(c for c in contacts_list if c["id"] == c1_id)
        assert c1_updated["is_primary"] is False

        # 4. Delete Contact 2
        del_res = await client.delete(f"/api/v1/parties/{party_id}/contacts/{c2_id}", headers=headers)
        assert del_res.status_code == 204

        # Verify only 1 contact remains
        contacts_after = (await client.get(f"/api/v1/parties/{party_id}/contacts", headers=headers)).json()
        assert len(contacts_after) == 1
        assert contacts_after[0]["id"] == c1_id


@pytest.mark.asyncio
async def test_intercompany_entity_linkage(db_session: AsyncSession):
    """Verify linking a party to an internal tenant company for inter-company netting."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = Company(id=uuid.uuid4(), name="Company A", code=f"IC_A_{uuid.uuid4().hex[:4]}")
        comp_b = Company(id=uuid.uuid4(), name="Company B (Affiliate)", code=f"IC_B_{uuid.uuid4().hex[:4]}")
        db_session.add_all([comp_a, comp_b])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a.id, {"allow_registration": True})

        username = f"ic_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "IC Tester", "company_id": str(comp_a.id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create Party in Company A linked to internal Company B
        res = await client.post(
            "/api/v1/parties/",
            json={
                "name": "Sister Affiliate Corp",
                "is_company": True,
                "is_customer": True,
                "is_vendor": True,
                "linked_company_id": str(comp_b.id),
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["linked_company_id"] == str(comp_b.id)
        assert data["linked_company_name"] == "Company B (Affiliate)"

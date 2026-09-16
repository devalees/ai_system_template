"""Comprehensive tests for Composite Addresses & Geographic Locations."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.lookups.models import Country, City


@pytest.mark.asyncio
async def test_address_creation_and_formatting(db_session: AsyncSession):
    """Verify address creation, city/country linkage, and formatted string generation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup tenant
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Address Test Co", code=f"ADR_{comp_id.hex[:4]}"))
        
        # Add Country & City
        country = Country(company_id=comp_id, code="EG", name="Egypt")
        city = City(company_id=comp_id, name="Cairo", country=country)
        db_session.add_all([country, city])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"addr_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Addr Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        target_entity_id = uuid.uuid4()
        payload = {
            "res_model": "Partner",
            "res_id": str(target_entity_id),
            "title": "Main Office",
            "address_type": "headquarters",
            "is_default": True,
            "street1": "10 Tahrir Square",
            "street2": "Floor 5, Suite 502",
            "postal_code": "11511",
            "city_id": str(city.id),
            "country_id": str(country.id),
            "geo_lat": 30.0444,
            "geo_lng": 31.2357,
        }

        res = await client.post("/api/v1/addresses/", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Main Office"
        assert data["city_name"] == "Cairo"
        assert data["country_name"] == "Egypt"
        assert data["is_default"] is True
        assert "10 Tahrir Square" in data["formatted_address"]
        assert "Cairo" in data["formatted_address"]
        assert "Egypt" in data["formatted_address"]


@pytest.mark.asyncio
async def test_single_default_guarantee(db_session: AsyncSession):
    """Verify that adding a new default address unsets previous defaults of the same type for that entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Default Test Co", code=f"DEF_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"def_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Def Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        target_entity_id = uuid.uuid4()

        # 1. Create first default billing address
        addr1_res = await client.post(
            "/api/v1/addresses/",
            json={
                "res_model": "Partner",
                "res_id": str(target_entity_id),
                "title": "First Billing",
                "address_type": "billing",
                "is_default": True,
                "street1": "Old Street 1",
            },
            headers=headers,
        )
        addr1_id = addr1_res.json()["id"]
        assert addr1_res.json()["is_default"] is True

        # 2. Create second default billing address for same entity
        addr2_res = await client.post(
            "/api/v1/addresses/",
            json={
                "res_model": "Partner",
                "res_id": str(target_entity_id),
                "title": "Second Billing",
                "address_type": "billing",
                "is_default": True,
                "street1": "New Street 2",
            },
            headers=headers,
        )
        addr2_id = addr2_res.json()["id"]
        assert addr2_res.json()["is_default"] is True

        # 3. Verify addr1 is now is_default=False
        check1 = await client.get(f"/api/v1/addresses/{addr1_id}", headers=headers)
        assert check1.json()["is_default"] is False

        # 4. Resolve default endpoint
        default_res = await client.get(
            f"/api/v1/addresses/entity/Partner/{target_entity_id}/default?address_type=billing",
            headers=headers,
        )
        assert default_res.status_code == 200
        assert default_res.json()["id"] == addr2_id


@pytest.mark.asyncio
async def test_address_update_and_soft_delete(db_session: AsyncSession):
    """Verify updating address fields and soft-deleting addresses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="CRUD Test Co", code=f"CRU_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"crud_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "CRUD Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create
        create_res = await client.post(
            "/api/v1/addresses/",
            json={"street1": "Warehouse Road 1", "address_type": "warehouse"},
            headers=headers,
        )
        addr_id = create_res.json()["id"]

        # Patch
        patch_res = await client.patch(
            f"/api/v1/addresses/{addr_id}",
            json={"street2": "Dock B", "geo_lat": 29.98, "geo_lng": 31.15},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["street2"] == "Dock B"
        assert patch_res.json()["geo_lat"] == 29.98

        # Delete
        del_res = await client.delete(f"/api/v1/addresses/{addr_id}", headers=headers)
        assert del_res.status_code == 204

        # Verify not found
        get_res = await client.get(f"/api/v1/addresses/{addr_id}", headers=headers)
        assert get_res.status_code == 404

"""Automated test suite for Lookups & Master Data Module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.lookups.fixtures import seed_iso_data
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_lookups_seeding_and_idempotency(db_session: AsyncSession):
    """Verify ISO seed fixtures bootstrap successfully and are idempotent."""
    company_id = uuid.uuid4()

    # 1. Initial Seed
    first_run = await seed_iso_data(db_session, company_id)
    assert first_run["currencies"] >= 8
    assert first_run["countries"] >= 9
    assert first_run["uom"] >= 7
    assert first_run["tax_types"] >= 5
    assert first_run["tags"] >= 4

    # 2. Re-run Seeding (Idempotency Check)
    second_run = await seed_iso_data(db_session, company_id)
    assert second_run["currencies"] == 0
    assert second_run["countries"] == 0
    assert second_run["uom"] == 0
    assert second_run["tax_types"] == 0
    assert second_run["tags"] == 0


@pytest.mark.asyncio
async def test_lookups_endpoints_and_multitenancy(db_session: AsyncSession):
    """Verify HTTP CRUD endpoints for lookups and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}"),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}"),
        ])
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", company_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", company_b, {"allow_registration": True})

        # 1. Register Tenant A
        user_a = f"tenant_lookup_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@test.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Tenant A Lookups",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # 2. Register Tenant B
        user_b = f"tenant_lookup_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@test.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Tenant B Lookups",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 3. Tenant A triggers seed endpoint
        res_seed_a = await client.post("/api/v1/lookups/seed", headers=headers_a)
        assert res_seed_a.status_code == 200
        seed_data = res_seed_a.json()
        assert seed_data["currencies"] >= 8

        # 4. Tenant A searches for country
        res_countries = await client.get("/api/v1/lookups/countries?search=Egypt", headers=headers_a)
        assert res_countries.status_code == 200
        countries = res_countries.json()
        assert len(countries) == 1
        egypt_id = countries[0]["id"]
        assert countries[0]["code"] == "EGY"

        # 5. Tenant A creates City linked to Egypt
        res_city = await client.post(
            "/api/v1/lookups/cities",
            headers=headers_a,
            json={
                "name": "Cairo",
                "country_id": egypt_id,
                "state_or_province": "Cairo Governorate",
                "postal_code": "11511",
            },
        )
        assert res_city.status_code == 201
        assert res_city.json()["name"] == "Cairo"

        # 6. Tenant A creates custom Tag
        res_tag = await client.post(
            "/api/v1/lookups/tags",
            headers=headers_a,
            json={"name": "CustomA-Tag", "color": "#123456", "model_target": "lead"},
        )
        assert res_tag.status_code == 201

        # 7. Tenant B queries tags -> must NOT see Tenant A's tag
        res_tags_b = await client.get("/api/v1/lookups/tags", headers=headers_b)
        assert res_tags_b.status_code == 200
        tags_b = res_tags_b.json()
        assert not any(t["name"] == "CustomA-Tag" for t in tags_b)

        # 8. Test UOM category filtering for Tenant A
        res_uom_weight = await client.get("/api/v1/lookups/uom?category=weight", headers=headers_a)
        assert res_uom_weight.status_code == 200
        weight_uoms = res_uom_weight.json()
        assert len(weight_uoms) >= 2
        assert all(u["category"] == "weight" for u in weight_uoms)

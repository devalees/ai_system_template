"""Comprehensive unit and integration tests for Unit of Measure & Conversion Matrix."""

import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_uom_category_and_unit_crud(db_session: AsyncSession):
    """Verify category creation, reference unit enforcement, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup Company A and Company B
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="UOM Co A", code=f"UA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="UOM Co B", code=f"UB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"uom_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "UOM Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"uom_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "UOM Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates "Weight" category
        res_cat = await client.post(
            "/api/v1/uom/categories",
            json={"name": "Weight", "description": "Mass and heavy material measures"},
            headers=headers_a,
        )
        assert res_cat.status_code == 201, res_cat.text
        cat_id = res_cat.json()["id"]

        # 2. Company A creates Reference Unit "Kilogram" (ratio=1.0)
        res_kg = await client.post(
            "/api/v1/uom/units",
            json={
                "category_id": cat_id,
                "name": "Kilogram",
                "code": "kg",
                "symbol": "kg",
                "uom_type": "reference",
                "ratio": 1.0,
                "rounding_precision": 0.01,
            },
            headers=headers_a,
        )
        assert res_kg.status_code == 201, res_kg.text
        kg_id = res_kg.json()["id"]

        # 3. Company A creates Bigger Unit "Metric Ton" (1 t = 1000 kg)
        res_t = await client.post(
            "/api/v1/uom/units",
            json={
                "category_id": cat_id,
                "name": "Metric Ton",
                "code": "t",
                "symbol": "t",
                "uom_type": "bigger",
                "ratio": 1000.0,
                "rounding_precision": 0.001,
            },
            headers=headers_a,
        )
        assert res_t.status_code == 201, res_t.text

        # 4. Company A creates Smaller Unit "Gram" (1000 g = 1 kg)
        res_g = await client.post(
            "/api/v1/uom/units",
            json={
                "category_id": cat_id,
                "name": "Gram",
                "code": "g",
                "symbol": "g",
                "uom_type": "smaller",
                "ratio": 1000.0,
                "rounding_precision": 0.1,
            },
            headers=headers_a,
        )
        assert res_g.status_code == 201, res_g.text

        # 5. Company A lists units
        res_units_a = await client.get(f"/api/v1/uom/units?category_id={cat_id}", headers=headers_a)
        assert res_units_a.status_code == 200
        assert len(res_units_a.json()) == 3

        # 6. Company B lists categories & units -> must see 0 (tenant isolation)
        res_cat_b = await client.get("/api/v1/uom/categories", headers=headers_b)
        assert res_cat_b.status_code == 200
        assert len(res_cat_b.json()) == 0

        res_units_b = await client.get("/api/v1/uom/units", headers=headers_b)
        assert res_units_b.status_code == 200
        assert len(res_units_b.json()) == 0


@pytest.mark.asyncio
async def test_uom_intra_category_conversion(db_session: AsyncSession):
    """Verify conversion math across reference, bigger, and smaller units in the same category."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Conversion Co", code=f"CV_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"cv_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Conversion Tester", "company_id": str(comp_id)},
        )
        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Category: Weight
        res_cat = await client.post("/api/v1/uom/categories", json={"name": "Weight"}, headers=headers)
        cat_id = res_cat.json()["id"]

        # kg (ref), t (bigger 1000), g (smaller 1000)
        await client.post(
            "/api/v1/uom/units",
            json={"category_id": cat_id, "name": "Kilogram", "code": "kg", "uom_type": "reference", "ratio": 1.0, "rounding_precision": 0.0001},
            headers=headers,
        )
        await client.post(
            "/api/v1/uom/units",
            json={"category_id": cat_id, "name": "Metric Ton", "code": "t", "uom_type": "bigger", "ratio": 1000.0, "rounding_precision": 0.0001},
            headers=headers,
        )
        await client.post(
            "/api/v1/uom/units",
            json={"category_id": cat_id, "name": "Gram", "code": "g", "uom_type": "smaller", "ratio": 1000.0, "rounding_precision": 0.01},
            headers=headers,
        )

        # 1. Convert 2.5 Tons -> Kilograms (Expected: 2500 kg)
        res_t_to_kg = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 2.5, "from_uom_code": "t", "to_uom_code": "kg"},
            headers=headers,
        )
        assert res_t_to_kg.status_code == 200, res_t_to_kg.text
        data = res_t_to_kg.json()
        assert float(data["converted_quantity"]) == 2500.0
        assert data["method"] == "intra_category"

        # 2. Convert 2.5 Tons -> Grams (Expected: 2,500,000 g)
        res_t_to_g = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 2.5, "from_uom_code": "t", "to_uom_code": "g"},
            headers=headers,
        )
        assert res_t_to_g.status_code == 200
        assert float(res_t_to_g.json()["converted_quantity"]) == 2500000.0

        # 3. Convert 500 Grams -> Kilograms (Expected: 0.5 kg)
        res_g_to_kg = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 500.0, "from_uom_code": "g", "to_uom_code": "kg"},
            headers=headers,
        )
        assert res_g_to_kg.status_code == 200
        assert float(res_g_to_kg.json()["converted_quantity"]) == 0.5

        # 4. Identity conversion: 10 kg -> 10 kg
        res_id = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 10.0, "from_uom_code": "kg", "to_uom_code": "kg"},
            headers=headers,
        )
        assert res_id.status_code == 200
        assert float(res_id.json()["converted_quantity"]) == 10.0
        assert res_id.json()["method"] == "identity"


@pytest.mark.asyncio
async def test_uom_explicit_and_cross_category_conversion(db_session: AsyncSession):
    """Verify cross-category conversion rules (e.g. Volume -> Weight via density multiplier)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Density Co", code=f"DS_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"ds_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Density Tester", "company_id": str(comp_id)},
        )
        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Category 1: Weight (kg)
        res_w = await client.post("/api/v1/uom/categories", json={"name": "Weight"}, headers=headers)
        cat_w_id = res_w.json()["id"]
        res_kg = await client.post(
            "/api/v1/uom/units",
            json={"category_id": cat_w_id, "name": "Kilogram", "code": "kg", "uom_type": "reference", "ratio": 1.0, "rounding_precision": 0.01},
            headers=headers,
        )
        kg_id = res_kg.json()["id"]

        # Category 2: Volume (L)
        res_v = await client.post("/api/v1/uom/categories", json={"name": "Volume"}, headers=headers)
        cat_v_id = res_v.json()["id"]
        res_l = await client.post(
            "/api/v1/uom/units",
            json={"category_id": cat_v_id, "name": "Liter", "code": "L", "uom_type": "reference", "ratio": 1.0, "rounding_precision": 0.01},
            headers=headers,
        )
        l_id = res_l.json()["id"]

        # 1. Attempt conversion across categories before rule is set -> 400 Validation Error
        res_fail = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 10.0, "from_uom_code": "L", "to_uom_code": "kg"},
            headers=headers,
        )
        assert res_fail.status_code == 400

        # 2. Register explicit cross-category rule: 1 Liter = 0.92 Kilogram (Olive Oil density)
        res_rule = await client.post(
            "/api/v1/uom/conversion-rules",
            json={"from_uom_id": l_id, "to_uom_id": kg_id, "ratio": 0.92},
            headers=headers,
        )
        assert res_rule.status_code == 201, res_rule.text

        # 3. Convert 10 Liters -> Kilograms (Expected: 10 * 0.92 = 9.20 kg)
        res_conv = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 10.0, "from_uom_code": "L", "to_uom_code": "kg"},
            headers=headers,
        )
        assert res_conv.status_code == 200, res_conv.text
        assert float(res_conv.json()["converted_quantity"]) == 9.20
        assert res_conv.json()["method"] == "explicit_rule"

        # 4. Inverse rule conversion: 9.20 Kilograms -> Liters (Expected: 9.20 / 0.92 = 10.00 L)
        res_inv = await client.post(
            "/api/v1/uom/convert",
            json={"quantity": 9.20, "from_uom_code": "kg", "to_uom_code": "L"},
            headers=headers,
        )
        assert res_inv.status_code == 200, res_inv.text
        assert float(res_inv.json()["converted_quantity"]) == 10.0
        assert res_inv.json()["method"] == "explicit_rule_inverse"

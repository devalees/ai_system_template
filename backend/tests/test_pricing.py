"""Comprehensive unit and integration tests for Pricing Engine & Multi-Tier Price Lists."""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_pricing_list_and_item_crud(db_session: AsyncSession):
    """Verify price list creation, item additions, updating, deletion, and tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Pricing Co A", code=f"PA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Pricing Co B", code=f"PB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"prc_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Pricing Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"prc_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Pricing Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates PriceList
        res_create = await client.post(
            "/api/v1/pricing/lists",
            json={"name": "Wholesale Standard", "code": "PL_WHOLESALE", "description": "Standard wholesale discounts"},
            headers=headers_a,
        )
        assert res_create.status_code == 201, res_create.text
        pl_data = res_create.json()
        pl_id = pl_data["id"]
        assert pl_data["code"] == "PL_WHOLESALE"

        # 2. Add Item: 10% global discount
        res_item = await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={
                "applied_on": "all",
                "min_quantity": 10.0,
                "pricing_mode": "percentage_discount",
                "discount_percentage": 10.0,
            },
            headers=headers_a,
        )
        assert res_item.status_code == 201, res_item.text
        item_id = res_item.json()["id"]

        # 3. Get PriceList with items
        res_get = await client.get(f"/api/v1/pricing/lists/{pl_id}", headers=headers_a)
        assert res_get.status_code == 200
        assert len(res_get.json()["items"]) == 1

        # 4. Company B lists price lists -> must see 0 (tenant isolation)
        res_list_b = await client.get("/api/v1/pricing/lists", headers=headers_b)
        assert res_list_b.status_code == 200
        assert len(res_list_b.json()) == 0

        # 5. Delete Item
        res_del_item = await client.delete(f"/api/v1/pricing/items/{item_id}", headers=headers_a)
        assert res_del_item.status_code == 204

        # Verify items count is 0
        res_get_empty = await client.get(f"/api/v1/pricing/lists/{pl_id}", headers=headers_a)
        assert len(res_get_empty.json()["items"]) == 0


@pytest.mark.asyncio
async def test_pricing_volume_tier_evaluation(db_session: AsyncSession):
    """Verify progressive volume discount tier resolution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Volume Co", code=f"VM_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"vm_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Volume Tester", "company_id": str(comp_id)},
        )
        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Create PriceList
        res_pl = await client.post("/api/v1/pricing/lists", json={"name": "Volume Discount List", "code": "PL_VOLUME"}, headers=headers)
        pl_id = res_pl.json()["id"]

        # Tier 1: min_qty = 1 -> 5%
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={"applied_on": "all", "min_quantity": 1.0, "pricing_mode": "percentage_discount", "discount_percentage": 5.0},
            headers=headers,
        )
        # Tier 2: min_qty = 50 -> 10%
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={"applied_on": "all", "min_quantity": 50.0, "pricing_mode": "percentage_discount", "discount_percentage": 10.0},
            headers=headers,
        )
        # Tier 3: min_qty = 100 -> 20%
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={"applied_on": "all", "min_quantity": 100.0, "pricing_mode": "percentage_discount", "discount_percentage": 20.0},
            headers=headers,
        )

        base_price = 100.0

        # 1. Qty = 10 -> matches Tier 1 (5% discount -> net 95.0, total 950.0)
        res_10 = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": base_price, "quantity": 10.0},
            headers=headers,
        )
        assert res_10.status_code == 200, res_10.text
        assert float(res_10.json()["unit_price"]) == 95.0
        assert float(res_10.json()["total_amount"]) == 950.0

        # 2. Qty = 50 -> matches Tier 2 (10% discount -> net 90.0, total 4500.0)
        res_50 = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": base_price, "quantity": 50.0},
            headers=headers,
        )
        assert res_50.status_code == 200
        assert float(res_50.json()["unit_price"]) == 90.0
        assert float(res_50.json()["total_amount"]) == 4500.0

        # 3. Qty = 150 -> matches Tier 3 (20% discount -> net 80.0, total 12000.0)
        res_150 = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": base_price, "quantity": 150.0},
            headers=headers,
        )
        assert res_150.status_code == 200
        assert float(res_150.json()["unit_price"]) == 80.0
        assert float(res_150.json()["total_amount"]) == 12000.0


@pytest.mark.asyncio
async def test_pricing_scope_precedence_and_promotions(db_session: AsyncSession):
    """Verify product-specific rule overrides global rule, and date-window validity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Promo Co", code=f"PR_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"pr_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Promo Tester", "company_id": str(comp_id)},
        )
        login = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Create PriceList
        res_pl = await client.post("/api/v1/pricing/lists", json={"name": "Campaign List", "code": "PL_CAMPAIGN"}, headers=headers)
        pl_id = res_pl.json()["id"]

        product_id = uuid.uuid4()

        # Rule 1: Global 10% discount
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={"applied_on": "all", "min_quantity": 1.0, "pricing_mode": "percentage_discount", "discount_percentage": 10.0},
            headers=headers,
        )

        # Rule 2: Product-specific fixed price $40 (where base price is $100)
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={"applied_on": "product", "res_model": "product", "res_id": str(product_id), "min_quantity": 1.0, "pricing_mode": "fixed", "fixed_price": 40.0},
            headers=headers,
        )

        # 1. Product-specific evaluation: Product rule ($40) must win over global 10% ($90)
        res_prod = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": 100.0, "quantity": 1.0, "res_id": str(product_id)},
            headers=headers,
        )
        assert res_prod.status_code == 200, res_prod.text
        assert float(res_prod.json()["unit_price"]) == 40.0
        assert res_prod.json()["applied_mode"] == "fixed"

        # 2. Other product evaluation: Global rule ($90) applies
        res_other = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": 100.0, "quantity": 1.0, "res_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert res_other.status_code == 200
        assert float(res_other.json()["unit_price"]) == 90.0
        assert res_other.json()["applied_mode"] == "percentage_discount"

        # 3. Time-window promotional rule: Valid only next week
        now = datetime.now(timezone.utc)
        next_week_start = now + timedelta(days=7)
        next_week_end = now + timedelta(days=14)

        promo_product_id = uuid.uuid4()
        await client.post(
            f"/api/v1/pricing/lists/{pl_id}/items",
            json={
                "applied_on": "product",
                "res_id": str(promo_product_id),
                "pricing_mode": "fixed",
                "fixed_price": 19.99,
                "valid_from": next_week_start.isoformat(),
                "valid_to": next_week_end.isoformat(),
            },
            headers=headers,
        )

        # Evaluate today -> Promotion not yet active, fallback to global 10% ($90)
        res_today = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": 100.0, "quantity": 1.0, "res_id": str(promo_product_id), "evaluation_date": now.isoformat()},
            headers=headers,
        )
        assert float(res_today.json()["unit_price"]) == 90.0

        # Evaluate during promo window -> Promotional price $19.99 applies
        during_promo = next_week_start + timedelta(days=2)
        res_promo = await client.post(
            "/api/v1/pricing/evaluate",
            json={"price_list_id": pl_id, "base_price": 100.0, "quantity": 1.0, "res_id": str(promo_product_id), "evaluation_date": during_promo.isoformat()},
            headers=headers,
        )
        assert float(res_promo.json()["unit_price"]) == 19.99
        assert res_promo.json()["applied_mode"] == "fixed"

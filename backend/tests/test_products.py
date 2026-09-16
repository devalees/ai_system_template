"""Comprehensive unit and integration tests for Product & Item Master Data and Upstream Integration."""

import uuid
import pytest
from decimal import Decimal
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.settings.service import SettingsService
from modules.base.uom.models import UOMCategory, UOMUnit
from modules.base.parties.models import Party
from modules.base.lookups.models import Currency


@pytest.mark.asyncio
async def test_product_crud_and_isolation(db_session: AsyncSession):
    """Verify product creation, detail retrieval, updates, duplicate code rejection, tenant isolation, and soft delete."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Product Corp A", code=f"PCA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Product Corp B", code=f"PCB_{comp_b.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register Admin A
        user_a = f"prod_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Prod Admin A", "company_id": str(comp_a)},
        )
        u_a = (await db_session.execute(select(User).where(User.username == user_a))).scalar_one()
        u_a.is_superuser = True
        await db_session.commit()

        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register Admin B
        user_b = f"prod_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Prod Admin B", "company_id": str(comp_b)},
        )
        u_b = (await db_session.execute(select(User).where(User.username == user_b))).scalar_one()
        u_b.is_superuser = True
        await db_session.commit()

        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # Seed UoM Unit for Company A
        cat_a = UOMCategory(company_id=comp_a, name="Unit Category A")
        db_session.add(cat_a)
        await db_session.flush()
        uom_a = UOMUnit(
            company_id=comp_a,
            category_id=cat_a.id,
            name="Piece",
            code="PCS",
            symbol="pc",
            uom_type="reference",
            ratio=Decimal("1.0000"),
        )
        db_session.add(uom_a)
        await db_session.commit()

        # 1. Company A creates product
        res_create = await client.post(
            "/api/v1/products",
            json={
                "code": "PROD-001",
                "name": "Industrial Drill",
                "description": "Heavy-duty electric drill",
                "product_type": "storable",
                "uom_id": str(uom_a.id),
                "sale_price": 250.00,
                "cost_price": 140.00,
                "sale_tax_ids": [],
                "purchase_tax_ids": [],
                "is_saleable": True,
                "is_purchasable": True,
                "is_active": True,
            },
            headers=headers_a,
        )
        assert res_create.status_code == 201, res_create.text
        prod_data = res_create.json()
        prod_id = prod_data["id"]
        assert prod_data["code"] == "PROD-001"
        assert float(prod_data["sale_price"]) == 250.0
        assert prod_data["uom_name"] == "Piece"

        # 2. Duplicate code in Company A rejected with 409 Conflict
        res_dup = await client.post(
            "/api/v1/products",
            json={
                "code": "PROD-001",
                "name": "Duplicate Drill",
                "uom_id": str(uom_a.id),
            },
            headers=headers_a,
        )
        assert res_dup.status_code == 409

        # 3. Retrieve detail
        res_get = await client.get(f"/api/v1/products/{prod_id}", headers=headers_a)
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "Industrial Drill"

        # 4. Partial update (patch sale price)
        res_patch = await client.patch(
            f"/api/v1/products/{prod_id}",
            json={"sale_price": 275.00, "name": "Industrial Drill Pro"},
            headers=headers_a,
        )
        assert res_patch.status_code == 200
        assert float(res_patch.json()["sale_price"]) == 275.0
        assert res_patch.json()["name"] == "Industrial Drill Pro"

        # 5. Defaults endpoint
        res_def = await client.get(f"/api/v1/products/{prod_id}/defaults?for_operation=sale", headers=headers_a)
        assert res_def.status_code == 200
        defaults = res_def.json()
        assert defaults["name"] == "Industrial Drill Pro"
        assert float(defaults["unit_price"]) == 275.0
        assert defaults["uom_id"] == str(uom_a.id)

        # 6. Tenant isolation: Company B cannot see Company A's product
        res_iso = await client.get(f"/api/v1/products/{prod_id}", headers=headers_b)
        assert res_iso.status_code == 404

        # 7. Soft delete product
        res_del = await client.delete(f"/api/v1/products/{prod_id}", headers=headers_a)
        assert res_del.status_code == 204

        # Verify not in list
        res_list = await client.get("/api/v1/products", headers=headers_a)
        assert res_list.status_code == 200
        assert not any(p["id"] == prod_id for p in res_list.json())


@pytest.mark.asyncio
async def test_sales_and_purchase_order_product_integration(db_session: AsyncSession):
    """Verify sales and purchase lines automatically populate name, price, uom, and taxes from Product."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Integrated Trading Co", code=f"ITC_{comp_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        # Register User
        uname = f"trade_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{uname}@test.com", "username": uname, "password": "Password123!", "full_name": "Trader", "company_id": str(comp_id)},
        )
        u_trade = (await db_session.execute(select(User).where(User.username == uname))).scalar_one()
        u_trade.is_superuser = True
        await db_session.commit()

        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": uname, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Seed master data: Currency, Partner, UoMs
        curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$")
        db_session.add(curr)
        party = Party(company_id=comp_id, name="Global Partner LLC", is_customer=True, is_vendor=True)
        db_session.add(party)
        uom_cat = UOMCategory(company_id=comp_id, name="General Units")
        db_session.add(uom_cat)
        await db_session.flush()

        sale_uom = UOMUnit(
            company_id=comp_id,
            category_id=uom_cat.id,
            name="Box of 10",
            code="BOX10",
            symbol="box",
            uom_type="bigger",
            ratio=Decimal("10.0000"),
        )
        purchase_uom = UOMUnit(
            company_id=comp_id,
            category_id=uom_cat.id,
            name="Pallet",
            code="PALLET",
            symbol="plt",
            uom_type="bigger",
            ratio=Decimal("100.0000"),
        )
        db_session.add(sale_uom)
        db_session.add(purchase_uom)
        await db_session.commit()

        # Create Catalog Product
        res_prod = await client.post(
            "/api/v1/products",
            json={
                "code": "ITEM-AUTO-01",
                "name": "Precision Sensor Unit",
                "product_type": "storable",
                "uom_id": str(sale_uom.id),
                "purchase_uom_id": str(purchase_uom.id),
                "sale_price": 500.00,
                "cost_price": 320.00,
                "sale_tax_ids": [str(uuid.uuid4())],
                "purchase_tax_ids": [str(uuid.uuid4())],
                "is_saleable": True,
                "is_purchasable": True,
            },
            headers=headers,
        )
        assert res_prod.status_code == 201, res_prod.text
        product_id = res_prod.json()["id"]

        # 1. Create Sales Order line specifying ONLY product_id and quantity
        res_so = await client.post(
            "/api/v1/sales/orders",
            json={
                "party_id": str(party.id),
                "order_date": "2026-09-16",
                "currency_id": str(curr.id),
                "lines": [
                    {
                        "product_id": product_id,
                        "quantity": 3.0,
                    }
                ],
            },
            headers=headers,
        )
        assert res_so.status_code == 201, res_so.text
        so_data = res_so.json()
        so_line = so_data["lines"][0]
        assert so_line["product_id"] == product_id
        assert so_line["name"] == "Precision Sensor Unit"
        assert float(so_line["unit_price"]) == 500.0
        assert so_line["uom_id"] == str(sale_uom.id)
        assert float(so_line["price_subtotal"]) == 1500.0  # 3 * 500

        # 2. Create Purchase Order line specifying ONLY product_id and quantity
        res_po = await client.post(
            "/api/v1/purchases/orders",
            json={
                "party_id": str(party.id),
                "order_date": "2026-09-16",
                "currency_id": str(curr.id),
                "lines": [
                    {
                        "product_id": product_id,
                        "quantity": 5.0,
                    }
                ],
            },
            headers=headers,
        )
        assert res_po.status_code == 201, res_po.text
        po_data = res_po.json()
        po_line = po_data["lines"][0]
        assert po_line["product_id"] == product_id
        assert po_line["name"] == "Precision Sensor Unit"
        assert float(po_line["unit_price"]) == 320.0  # Cost price
        assert po_line["uom_id"] == str(purchase_uom.id)  # Purchase UoM
        assert float(po_line["price_subtotal"]) == 1600.0  # 5 * 320


@pytest.mark.asyncio
async def test_account_move_line_with_product_id(db_session: AsyncSession):
    """Verify AccountMoveLine persists and serializes product_id correctly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Accounting Prod Corp", code=f"APC_{comp_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        uname = f"acc_prod_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{uname}@test.com", "username": uname, "password": "Password123!", "full_name": "Acc Master", "company_id": str(comp_id)},
        )
        u_acc = (await db_session.execute(select(User).where(User.username == uname))).scalar_one()
        u_acc.is_superuser = True
        await db_session.commit()

        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": uname, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Seed master data: Currency, Journal, Accounts, UoM, Product
        curr = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$")
        db_session.add(curr)
        uom_cat = UOMCategory(company_id=comp_id, name="Count")
        db_session.add(uom_cat)
        await db_session.flush()

        unit_uom = UOMUnit(
            company_id=comp_id,
            category_id=uom_cat.id,
            name="Each",
            code="EA",
            symbol="ea",
            uom_type="reference",
            ratio=Decimal("1.0000"),
        )
        db_session.add(unit_uom)
        await db_session.commit()

        # Create Product
        res_prod = await client.post(
            "/api/v1/products",
            json={
                "code": "PROD-ACC-01",
                "name": "Consulting Package",
                "product_type": "service",
                "uom_id": str(unit_uom.id),
                "sale_price": 1000.00,
                "cost_price": 0.00,
            },
            headers=headers,
        )
        assert res_prod.status_code == 201
        prod_id = res_prod.json()["id"]

        # Create Journal & Accounts
        res_j = await client.post(
            "/api/v1/accounting/journals",
            json={"code": "GEN", "name": "General Operations", "type": "general"},
            headers=headers,
        )
        journal_id = res_j.json()["id"]

        res_acc1 = await client.post(
            "/api/v1/accounting/accounts",
            json={"code": "1001", "name": "Cash at Bank", "account_type": "asset_current"},
            headers=headers,
        )
        res_acc2 = await client.post(
            "/api/v1/accounting/accounts",
            json={"code": "4001", "name": "Service Revenue", "account_type": "income"},
            headers=headers,
        )
        acc1_id = res_acc1.json()["id"]
        acc2_id = res_acc2.json()["id"]

        # Create Move with product_id on line
        res_move = await client.post(
            "/api/v1/accounting/moves",
            json={
                "move_type": "entry",
                "date": "2026-09-16",
                "journal_id": journal_id,
                "currency_id": str(curr.id),
                "ref": "INV-PROD-TEST",
                "lines": [
                    {
                        "account_id": acc1_id,
                        "name": "Cash receipt",
                        "debit": 1000.00,
                        "credit": 0.00,
                    },
                    {
                        "account_id": acc2_id,
                        "product_id": prod_id,
                        "name": "Consulting Revenue",
                        "debit": 0.00,
                        "credit": 1000.00,
                    },
                ],
            },
            headers=headers,
        )
        assert res_move.status_code == 201, res_move.text
        move_data = res_move.json()
        credit_line = [l for l in move_data["lines"] if float(l["credit"]) == 1000.0][0]
        assert credit_line["product_id"] == prod_id

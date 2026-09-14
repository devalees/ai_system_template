"""Automated test suite for Lookups & Master Data Module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.lookups.fixtures import seed_iso_data
from modules.base.settings.service import SettingsService
from modules.base.documents.models import DocumentAttachment


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
    assert first_run["categories"] >= 5

    # 2. Re-run Seeding (Idempotency Check)
    second_run = await seed_iso_data(db_session, company_id)
    assert second_run["currencies"] == 0
    assert second_run["countries"] == 0
    assert second_run["uom"] == 0
    assert second_run["tax_types"] == 0
    assert second_run["tags"] == 0
    assert second_run["categories"] == 0


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


@pytest.mark.asyncio
async def test_hierarchical_category_engine_and_cycle_prevention(db_session: AsyncSession):
    """Verify recursive parent-child category tree, cycle prevention, and CategorizableMixin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Seed companies
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add_all([
            Company(id=comp_a, name="Cat Company A", code=f"CCA_{comp_a.hex[:4]}"),
            Company(id=comp_b, name="Cat Company B", code=f"CCB_{comp_b.hex[:4]}"),
        ])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register users
        user_a = f"cat_user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Cat User A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}", "X-Company-ID": str(comp_a)}

        user_b = f"cat_user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Cat User B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}", "X-Company-ID": str(comp_b)}

        # 2. Tenant A creates Root Category: "Corporate Documents"
        res_root = await client.post(
            "/api/v1/lookups/categories",
            headers=headers_a,
            json={
                "name": "Corporate Documents",
                "code": "CORP_DOCS",
                "res_model": "document",
                "parent_id": None,
                "description": "Top-level corporate documents folder",
                "color": "#3b82f6",
                "icon": "folder",
                "sequence": 10,
            },
        )
        assert res_root.status_code == 201
        root_data = res_root.json()
        root_id = root_data["id"]
        assert root_data["parent_id"] is None
        assert root_data["full_path"] == "Corporate Documents"

        # 3. Tenant A creates Sub-Category: "Legal Contracts" (parent = root_id)
        res_sub = await client.post(
            "/api/v1/lookups/categories",
            headers=headers_a,
            json={
                "name": "Legal Contracts",
                "code": "LEGAL_CONTRACTS",
                "res_model": "document",
                "parent_id": root_id,
                "description": "Commercial and vendor agreements",
                "color": "#10b981",
                "icon": "file-text",
                "sequence": 10,
            },
        )
        assert res_sub.status_code == 201
        sub_data = res_sub.json()
        sub_id = sub_data["id"]
        assert sub_data["parent_id"] == root_id
        assert sub_data["parent_name"] == "Corporate Documents"
        assert sub_data["full_path"] == "Corporate Documents / Legal Contracts"

        # 4. Tenant A creates 3rd level sub-sub-category: "Non-Disclosure Agreements"
        res_leaf = await client.post(
            "/api/v1/lookups/categories",
            headers=headers_a,
            json={
                "name": "Non-Disclosure Agreements",
                "code": "NDAS",
                "res_model": "document",
                "parent_id": sub_id,
                "description": "Standard bilateral and unilateral NDAs",
                "color": "#8b5cf6",
                "icon": "shield",
                "sequence": 5,
            },
        )
        assert res_leaf.status_code == 201
        leaf_data = res_leaf.json()
        leaf_id = leaf_data["id"]
        assert leaf_data["full_path"] == "Corporate Documents / Legal Contracts / Non-Disclosure Agreements"

        # 5. Verify Hierarchical Tree API
        res_tree = await client.get("/api/v1/lookups/categories/tree?res_model=document", headers=headers_a)
        assert res_tree.status_code == 200
        tree_nodes = res_tree.json()
        doc_root = next(n for n in tree_nodes if n["id"] == root_id)
        assert len(doc_root["children"]) >= 1
        legal_node = next(c for c in doc_root["children"] if c["id"] == sub_id)
        assert len(legal_node["children"]) >= 1
        nda_node = next(c for c in legal_node["children"] if c["id"] == leaf_id)
        assert nda_node["name"] == "Non-Disclosure Agreements"

        # 6. Verify Cycle Prevention
        # Attempt 1: Root category sets itself as parent
        res_cycle_self = await client.patch(
            f"/api/v1/lookups/categories/{root_id}",
            headers=headers_a,
            json={"parent_id": root_id},
        )
        assert res_cycle_self.status_code == 400
        assert "cannot be its own parent" in res_cycle_self.json()["error"]["message"]

        # Attempt 2: Root category sets descendant (sub_id) as parent
        res_cycle_descendant = await client.patch(
            f"/api/v1/lookups/categories/{root_id}",
            headers=headers_a,
            json={"parent_id": sub_id},
        )
        assert res_cycle_descendant.status_code == 400
        assert "circular tree reference" in res_cycle_descendant.json()["error"]["message"]

        # Attempt 3: Root category sets leaf (grandchild) as parent
        res_cycle_leaf = await client.patch(
            f"/api/v1/lookups/categories/{root_id}",
            headers=headers_a,
            json={"parent_id": leaf_id},
        )
        assert res_cycle_leaf.status_code == 400
        assert "circular tree reference" in res_cycle_leaf.json()["error"]["message"]

        # 7. Verify Multi-Tenant Isolation
        # Tenant B queries categories -> must NOT see Tenant A's categories
        res_tree_b = await client.get("/api/v1/lookups/categories/tree?res_model=document", headers=headers_b)
        assert res_tree_b.status_code == 200
        assert not any(n["id"] == root_id for n in res_tree_b.json())

        # Tenant B attempts to access Tenant A's category by ID -> 404
        res_forbidden = await client.get(f"/api/v1/lookups/categories/{root_id}", headers=headers_b)
        assert res_forbidden.status_code == 404

        # 8. Verify CategorizableMixin on DocumentAttachment
        doc = DocumentAttachment(
            company_id=comp_a,
            name="Confidential_NDA_2026.pdf",
            file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            file_size=1024,
            mime_type="application/pdf",
            storage_path="/tmp/nda.pdf",
            category_id=uuid.UUID(leaf_id),
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)
        assert doc.category_id == uuid.UUID(leaf_id)


@pytest.mark.asyncio
async def test_lookups_master_data_full_crud_and_patch(db_session: AsyncSession):
    """Verify full CRUD lifecycle (GET /{id}, PATCH /{id}, DELETE /{id}) across all master data lookups."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create test companies
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add_all([
            Company(id=comp_a, name="CRUD Co A", code=f"CRUDA_{comp_a.hex[:4]}"),
            Company(id=comp_b, name="CRUD Co B", code=f"CRUDB_{comp_b.hex[:4]}"),
        ])
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register and login Tenant A
        user_a = f"crud_user_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register and login Tenant B
        user_b = f"crud_user_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Country CRUD
        country_res = await client.post(
            "/api/v1/lookups/countries",
            headers=headers_a,
            json={"name": "Testland", "code": "TLD", "code_alpha2": "TL", "dialing_code": "+999", "currency_code": "TLD"},
        )
        assert country_res.status_code == 201
        country_id = country_res.json()["id"]

        # GET by ID
        get_c = await client.get(f"/api/v1/lookups/countries/{country_id}", headers=headers_a)
        assert get_c.status_code == 200
        assert get_c.json()["name"] == "Testland"

        # PATCH
        patch_c = await client.patch(
            f"/api/v1/lookups/countries/{country_id}",
            headers=headers_a,
            json={"name": "Testland Updated", "dialing_code": "+998"},
        )
        assert patch_c.status_code == 200
        assert patch_c.json()["name"] == "Testland Updated"
        assert patch_c.json()["dialing_code"] == "+998"

        # Tenant B cannot access Tenant A's country
        assert (await client.get(f"/api/v1/lookups/countries/{country_id}", headers=headers_b)).status_code == 404
        assert (await client.patch(f"/api/v1/lookups/countries/{country_id}", headers=headers_b, json={"name": "Hack"})).status_code == 404

        # 2. City CRUD
        city_res = await client.post(
            "/api/v1/lookups/cities",
            headers=headers_a,
            json={"name": "Test City", "country_id": country_id, "state_or_province": "Test State", "postal_code": "12345"},
        )
        assert city_res.status_code == 201
        city_id = city_res.json()["id"]

        # GET by ID
        get_city = await client.get(f"/api/v1/lookups/cities/{city_id}", headers=headers_a)
        assert get_city.status_code == 200
        assert get_city.json()["name"] == "Test City"

        # PATCH
        patch_city = await client.patch(
            f"/api/v1/lookups/cities/{city_id}",
            headers=headers_a,
            json={"name": "Test City Renamed", "postal_code": "54321"},
        )
        assert patch_city.status_code == 200
        assert patch_city.json()["name"] == "Test City Renamed"
        assert patch_city.json()["postal_code"] == "54321"

        # DELETE City (Soft delete)
        del_city = await client.delete(f"/api/v1/lookups/cities/{city_id}", headers=headers_a)
        assert del_city.status_code == 204
        assert (await client.get(f"/api/v1/lookups/cities/{city_id}", headers=headers_a)).status_code == 404

        # DELETE Country
        del_c = await client.delete(f"/api/v1/lookups/countries/{country_id}", headers=headers_a)
        assert del_c.status_code == 204
        assert (await client.get(f"/api/v1/lookups/countries/{country_id}", headers=headers_a)).status_code == 404

        # 3. Currency CRUD
        curr_res = await client.post(
            "/api/v1/lookups/currencies",
            headers=headers_a,
            json={"code": "XTL", "name": "Test Currency", "symbol": "XT", "decimal_places": 2, "is_base": False},
        )
        assert curr_res.status_code == 201
        curr_id = curr_res.json()["id"]

        get_curr = await client.get(f"/api/v1/lookups/currencies/{curr_id}", headers=headers_a)
        assert get_curr.status_code == 200
        assert get_curr.json()["code"] == "XTL"

        patch_curr = await client.patch(
            f"/api/v1/lookups/currencies/{curr_id}",
            headers=headers_a,
            json={"name": "Test Currency Revised", "decimal_places": 4},
        )
        assert patch_curr.status_code == 200
        assert patch_curr.json()["name"] == "Test Currency Revised"
        assert patch_curr.json()["decimal_places"] == 4

        del_curr = await client.delete(f"/api/v1/lookups/currencies/{curr_id}", headers=headers_a)
        assert del_curr.status_code == 204
        assert (await client.get(f"/api/v1/lookups/currencies/{curr_id}", headers=headers_a)).status_code == 404

        # 4. Unit of Measure (UOM) CRUD
        uom_res = await client.post(
            "/api/v1/lookups/uom",
            headers=headers_a,
            json={"name": "Megapack", "code": "MPK", "category": "packaging", "rounding_precision": 1.0},
        )
        assert uom_res.status_code == 201
        uom_id = uom_res.json()["id"]

        get_uom = await client.get(f"/api/v1/lookups/uom/{uom_id}", headers=headers_a)
        assert get_uom.status_code == 200
        assert get_uom.json()["name"] == "Megapack"

        patch_uom = await client.patch(
            f"/api/v1/lookups/uom/{uom_id}",
            headers=headers_a,
            json={"name": "Megapack XL", "rounding_precision": 0.5},
        )
        assert patch_uom.status_code == 200
        assert patch_uom.json()["name"] == "Megapack XL"
        assert patch_uom.json()["rounding_precision"] == 0.5

        del_uom = await client.delete(f"/api/v1/lookups/uom/{uom_id}", headers=headers_a)
        assert del_uom.status_code == 204
        assert (await client.get(f"/api/v1/lookups/uom/{uom_id}", headers=headers_a)).status_code == 404

        # 5. Tax Type CRUD
        tax_res = await client.post(
            "/api/v1/lookups/tax-types",
            headers=headers_a,
            json={"name": "Special Luxury Tax", "code": "SLT", "rate": 25.0, "is_inclusive": False},
        )
        assert tax_res.status_code == 201
        tax_id = tax_res.json()["id"]

        get_tax = await client.get(f"/api/v1/lookups/tax-types/{tax_id}", headers=headers_a)
        assert get_tax.status_code == 200
        assert get_tax.json()["name"] == "Special Luxury Tax"

        patch_tax = await client.patch(
            f"/api/v1/lookups/tax-types/{tax_id}",
            headers=headers_a,
            json={"name": "Special Luxury Tax Updated", "rate": 27.5, "is_inclusive": True},
        )
        assert patch_tax.status_code == 200
        assert patch_tax.json()["name"] == "Special Luxury Tax Updated"
        assert patch_tax.json()["rate"] == 27.5
        assert patch_tax.json()["is_inclusive"] is True

        del_tax = await client.delete(f"/api/v1/lookups/tax-types/{tax_id}", headers=headers_a)
        assert del_tax.status_code == 204
        assert (await client.get(f"/api/v1/lookups/tax-types/{tax_id}", headers=headers_a)).status_code == 404

        # 6. Tag CRUD
        tag_res = await client.post(
            "/api/v1/lookups/tags",
            headers=headers_a,
            json={"name": "High Priority QA", "color": "#ff0055", "model_target": "task"},
        )
        assert tag_res.status_code == 201
        tag_id = tag_res.json()["id"]

        get_tag = await client.get(f"/api/v1/lookups/tags/{tag_id}", headers=headers_a)
        assert get_tag.status_code == 200
        assert get_tag.json()["name"] == "High Priority QA"

        patch_tag = await client.patch(
            f"/api/v1/lookups/tags/{tag_id}",
            headers=headers_a,
            json={"name": "Critical QA", "color": "#00ff00"},
        )
        assert patch_tag.status_code == 200
        assert patch_tag.json()["name"] == "Critical QA"
        assert patch_tag.json()["color"] == "#00ff00"

        del_tag = await client.delete(f"/api/v1/lookups/tags/{tag_id}", headers=headers_a)
        assert del_tag.status_code == 204
        assert (await client.get(f"/api/v1/lookups/tags/{tag_id}", headers=headers_a)).status_code == 404


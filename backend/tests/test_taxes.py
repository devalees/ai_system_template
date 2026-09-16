"""Comprehensive unit and integration tests for Tax Engine & Fiscal Positions."""

import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_taxes_and_fiscal_positions_crud(db_session: AsyncSession):
    """Verify CRUD for taxes, fiscal positions, mapping rules, and tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_a = uuid.uuid4()
        comp_b = uuid.uuid4()
        db_session.add(Company(id=comp_a, name="Tax Co A", code=f"TA_{comp_a.hex[:4]}"))
        db_session.add(Company(id=comp_b, name="Tax Co B", code=f"TB_{comp_b.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_a, {"allow_registration": True})
        await SettingsService.update_settings(db_session, "identity_rbac", comp_b, {"allow_registration": True})

        # Register User A
        user_a = f"tax_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_a}@test.com", "username": user_a, "password": "Password123!", "full_name": "Tax Admin A", "company_id": str(comp_a)},
        )
        login_a = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_a, "password": "Password123!"})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Register User B
        user_b = f"tax_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_b}@test.com", "username": user_b, "password": "Password123!", "full_name": "Tax Admin B", "company_id": str(comp_b)},
        )
        login_b = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_b, "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # 1. Company A creates standard 15% VAT
        res_vat15 = await client.post(
            "/api/v1/taxes",
            json={
                "name": "Value Added Tax 15%",
                "code": "VAT_15",
                "tax_scope": "sales",
                "calculation_type": "percent",
                "amount": "15.0000",
                "is_inclusive": False,
                "include_base_amount": False,
                "sequence": 10,
            },
            headers=headers_a,
        )
        assert res_vat15.status_code == 201, res_vat15.text
        vat15_id = res_vat15.json()["id"]

        # 2. Company A creates 0% Export VAT
        res_vat0 = await client.post(
            "/api/v1/taxes",
            json={
                "name": "Export Zero Rate 0%",
                "code": "VAT_0_EXP",
                "tax_scope": "sales",
                "calculation_type": "percent",
                "amount": "0.0000",
                "is_inclusive": False,
                "include_base_amount": False,
                "sequence": 10,
            },
            headers=headers_a,
        )
        assert res_vat0.status_code == 201, res_vat0.text
        vat0_id = res_vat0.json()["id"]

        # 3. Company A creates Fiscal Position for Exports
        res_fp = await client.post(
            "/api/v1/taxes/fiscal-positions",
            json={
                "name": "Export Outside Jurisdiction",
                "code": "FP_EXPORT",
                "description": "Exempts international buyers from domestic VAT",
                "auto_apply": False,
                "vat_required": False,
                "note": "Export exempt per article 42",
            },
            headers=headers_a,
        )
        assert res_fp.status_code == 201, res_fp.text
        fp_id = res_fp.json()["id"]

        # 4. Add tax substitution rule: VAT15 -> VAT0
        res_rule = await client.post(
            f"/api/v1/taxes/fiscal-positions/{fp_id}/rules",
            json={"source_tax_id": vat15_id, "dest_tax_id": vat0_id},
            headers=headers_a,
        )
        assert res_rule.status_code == 201, res_rule.text
        rule_data = res_rule.json()
        assert rule_data["source_tax_id"] == vat15_id
        assert rule_data["dest_tax_id"] == vat0_id

        # 5. Get Fiscal Position and verify rules
        res_get_fp = await client.get(f"/api/v1/taxes/fiscal-positions/{fp_id}", headers=headers_a)
        assert res_get_fp.status_code == 200
        fp_data = res_get_fp.json()
        assert len(fp_data["rules"]) == 1
        assert fp_data["rules"][0]["source_tax_name"] == "Value Added Tax 15%"
        assert fp_data["rules"][0]["dest_tax_name"] == "Export Zero Rate 0%"

        # 6. Tenant isolation: User B cannot see User A's taxes
        res_b_list = await client.get("/api/v1/taxes", headers=headers_b)
        assert res_b_list.status_code == 200
        assert len(res_b_list.json()) == 0


@pytest.mark.asyncio
async def test_tax_calculation_exclusive_inclusive_and_compound(db_session: AsyncSession):
    """Verify exclusive, inclusive, and multi-tax compound calculations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Tax Calc Co", code=f"TC_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"tax_calc_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Tax Calc User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create 1: 10% Excise Duty (Compound: include_base_amount=True, sequence=10)
        res_excise = await client.post(
            "/api/v1/taxes",
            json={
                "name": "Excise Duty 10%",
                "code": "EXCISE_10",
                "calculation_type": "percent",
                "amount": "10.0000",
                "is_inclusive": False,
                "include_base_amount": True,
                "sequence": 10,
            },
            headers=headers,
        )
        excise_id = res_excise.json()["id"]

        # Create 2: 15% VAT (Exclusive, sequence=20)
        res_vat = await client.post(
            "/api/v1/taxes",
            json={
                "name": "VAT 15%",
                "code": "VAT_15",
                "calculation_type": "percent",
                "amount": "15.0000",
                "is_inclusive": False,
                "include_base_amount": False,
                "sequence": 20,
            },
            headers=headers,
        )
        vat_id = res_vat.json()["id"]

        # Create 3: 20% Inclusive VAT
        res_inc = await client.post(
            "/api/v1/taxes",
            json={
                "name": "Retail Inclusive 20%",
                "code": "INC_20",
                "calculation_type": "percent",
                "amount": "20.0000",
                "is_inclusive": True,
                "include_base_amount": False,
                "sequence": 10,
            },
            headers=headers,
        )
        inc_id = res_inc.json()["id"]

        # Case A: Compound Excise (10%) + VAT (15%) on unit price 100, qty 2 = 200 base
        # Excise = 10% of 200 = 20.00. Base becomes 220.
        # VAT = 15% of 220 = 33.00.
        # Total tax = 53.00, Subtotal = 200.00, Gross = 253.00.
        calc_compound = await client.post(
            "/api/v1/taxes/compute",
            json={
                "lines": [
                    {
                        "line_id": "line-comp-1",
                        "price_unit": "100.00",
                        "quantity": "2.0",
                        "discount_percentage": "0.0",
                        "tax_ids": [excise_id, vat_id],
                    }
                ],
                "currency_rounding": "0.01",
            },
            headers=headers,
        )
        assert calc_compound.status_code == 200, calc_compound.text
        comp_data = calc_compound.json()
        assert comp_data["subtotal"] == "200.00"
        assert comp_data["total_tax"] == "53.00"
        assert comp_data["total_amount"] == "253.00"
        assert len(comp_data["lines"][0]["tax_breakdown"]) == 2
        assert comp_data["lines"][0]["tax_breakdown"][0]["tax_amount"] == "20.00"
        assert comp_data["lines"][0]["tax_breakdown"][1]["tax_amount"] == "33.00"

        # Case B: 20% Inclusive tax on unit price 120, qty 1
        # Net base = 120 / 1.20 = 100.00.
        # Tax = 20.00. Total = 120.00.
        calc_inc = await client.post(
            "/api/v1/taxes/compute",
            json={
                "lines": [
                    {
                        "line_id": "line-inc-1",
                        "price_unit": "120.00",
                        "quantity": "1.0",
                        "discount_percentage": "0.0",
                        "tax_ids": [inc_id],
                    }
                ],
                "currency_rounding": "0.01",
            },
            headers=headers,
        )
        assert calc_inc.status_code == 200, calc_inc.text
        inc_data = calc_inc.json()
        assert inc_data["subtotal"] == "100.00"
        assert inc_data["total_tax"] == "20.00"
        assert inc_data["total_amount"] == "120.00"


@pytest.mark.asyncio
async def test_fiscal_position_tax_substitution_and_exemption(db_session: AsyncSession):
    """Verify fiscal positions replacing taxes or exempting lines."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Tax FP Co", code=f"TFP_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        user_name = f"tax_fp_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{user_name}@test.com", "username": user_name, "password": "Password123!", "full_name": "Tax FP User", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": user_name, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Base Tax: Standard VAT 15%
        res_vat15 = await client.post(
            "/api/v1/taxes",
            json={"name": "VAT 15%", "code": "VAT_15", "amount": "15.0000", "is_inclusive": False},
            headers=headers,
        )
        vat15_id = res_vat15.json()["id"]

        # 2. Reduced Tax: Reduced VAT 5%
        res_vat5 = await client.post(
            "/api/v1/taxes",
            json={"name": "VAT 5%", "code": "VAT_5", "amount": "5.0000", "is_inclusive": False},
            headers=headers,
        )
        vat5_id = res_vat5.json()["id"]

        # 3. Fiscal Position 1: Reduced Rate Zone (VAT15 -> VAT5)
        res_fp_reduced = await client.post(
            "/api/v1/taxes/fiscal-positions",
            json={
                "name": "Special Economic Zone",
                "code": "FP_SEZ",
                "rules": [{"source_tax_id": vat15_id, "dest_tax_id": vat5_id}],
            },
            headers=headers,
        )
        fp_reduced_id = res_fp_reduced.json()["id"]

        # 4. Fiscal Position 2: Diplomatic / Exempt Zone (VAT15 -> None)
        res_fp_exempt = await client.post(
            "/api/v1/taxes/fiscal-positions",
            json={
                "name": "Diplomatic Exemption",
                "code": "FP_DIPLOMATIC",
                "rules": [{"source_tax_id": vat15_id, "dest_tax_id": None}],
            },
            headers=headers,
        )
        fp_exempt_id = res_fp_exempt.json()["id"]

        # Compute line with price 100, qty 1
        # Without FP: VAT15 applies -> 15.00 tax
        res_normal = await client.post(
            "/api/v1/taxes/compute",
            json={"lines": [{"price_unit": "100.00", "quantity": "1.0", "tax_ids": [vat15_id]}]},
            headers=headers,
        )
        assert res_normal.json()["total_tax"] == "15.00"

        # With Reduced FP: VAT5 applies -> 5.00 tax
        res_reduced = await client.post(
            "/api/v1/taxes/compute",
            json={
                "lines": [{"price_unit": "100.00", "quantity": "1.0", "tax_ids": [vat15_id]}],
                "fiscal_position_id": fp_reduced_id,
            },
            headers=headers,
        )
        assert res_reduced.json()["total_tax"] == "5.00"
        assert res_reduced.json()["fiscal_position_applied"] == "Special Economic Zone"

        # With Exempt FP: VAT15 is removed -> 0.00 tax
        res_exempt = await client.post(
            "/api/v1/taxes/compute",
            json={
                "lines": [{"price_unit": "100.00", "quantity": "1.0", "tax_ids": [vat15_id]}],
                "fiscal_position_id": fp_exempt_id,
            },
            headers=headers,
        )
        assert res_exempt.json()["total_tax"] == "0.00"
        assert res_exempt.json()["fiscal_position_applied"] == "Diplomatic Exemption"

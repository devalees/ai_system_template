"""Comprehensive tests for Money, Multi-Currency & Historical FX Engine."""

import uuid
import pytest
from datetime import date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.settings.service import SettingsService
from modules.base.lookups.models import Currency
from modules.base.fx_engine.service import FXService


@pytest.mark.asyncio
async def test_direct_and_inverse_conversion(db_session: AsyncSession):
    """Verify exchange rate registration, auto-inverse calculation, and direct/inverse conversion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="FX Test Co", code=f"FX_{comp_id.hex[:4]}"))

        usd = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        egp = Currency(company_id=comp_id, code="EGP", name="Egyptian Pound", symbol="E£", decimal_places=2, is_base=False)
        db_session.add_all([usd, egp])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"fx_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "FX Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Register USD to EGP rate: 48.500000
        create_res = await client.post(
            "/api/v1/fx_engine/rates",
            json={
                "from_currency_id": str(usd.id),
                "to_currency_id": str(egp.id),
                "rate": "48.500000",
                "effective_date": "2026-03-01",
                "source": "central_bank",
            },
            headers=headers,
        )
        assert create_res.status_code == 201
        rate_data = create_res.json()
        assert rate_data["rate"] == "48.500000"
        # Inverse rate roughly 1 / 48.5 = 0.020619
        assert Decimal(rate_data["inverse_rate"]) > Decimal("0.020618")

        # 2. Direct conversion: 100 USD -> 4,850.00 EGP
        conv_res1 = await client.post(
            "/api/v1/fx_engine/convert",
            json={
                "amount": "100.00",
                "from_currency_id": str(usd.id),
                "to_currency_id": str(egp.id),
                "effective_date": "2026-03-15",
            },
            headers=headers,
        )
        assert conv_res1.status_code == 200
        res1_data = conv_res1.json()
        assert res1_data["converted_amount"] == "4850.00"
        assert res1_data["from_currency_code"] == "USD"
        assert res1_data["to_currency_code"] == "EGP"
        assert res1_data["triangulation_used"] is False

        # 3. Inverse conversion: 4,850 EGP -> ~100.00 USD
        conv_res2 = await client.post(
            "/api/v1/fx_engine/convert",
            json={
                "amount": "4850.00",
                "from_currency_id": str(egp.id),
                "to_currency_id": str(usd.id),
                "effective_date": "2026-03-15",
            },
            headers=headers,
        )
        assert conv_res2.status_code == 200
        res2_data = conv_res2.json()
        assert Decimal(res2_data["converted_amount"]) == Decimal("100.00")
        assert res2_data["from_currency_code"] == "EGP"
        assert res2_data["to_currency_code"] == "USD"


@pytest.mark.asyncio
async def test_triangulation_via_base_currency(db_session: AsyncSession):
    """Verify triangulation when converting EUR to EGP via USD base currency."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Triangulation Co", code=f"TR_{comp_id.hex[:4]}"))

        usd = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        eur = Currency(company_id=comp_id, code="EUR", name="Euro", symbol="€", decimal_places=2, is_base=False)
        egp = Currency(company_id=comp_id, code="EGP", name="Egyptian Pound", symbol="E£", decimal_places=2, is_base=False)
        db_session.add_all([usd, eur, egp])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"tr_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "TR Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. EUR -> USD = 1.080000
        await client.post(
            "/api/v1/fx_engine/rates",
            json={"from_currency_id": str(eur.id), "to_currency_id": str(usd.id), "rate": "1.080000", "effective_date": "2026-01-01"},
            headers=headers,
        )

        # 2. USD -> EGP = 50.000000
        await client.post(
            "/api/v1/fx_engine/rates",
            json={"from_currency_id": str(usd.id), "to_currency_id": str(egp.id), "rate": "50.000000", "effective_date": "2026-01-01"},
            headers=headers,
        )

        # 3. Convert 100 EUR -> EGP (100 * 1.08 * 50 = 5,400.00 EGP)
        conv_res = await client.post(
            "/api/v1/fx_engine/convert",
            json={"amount": "100.00", "from_currency_id": str(eur.id), "to_currency_id": str(egp.id), "effective_date": "2026-01-15"},
            headers=headers,
        )
        assert conv_res.status_code == 200
        data = conv_res.json()
        assert data["triangulation_used"] is True
        assert data["converted_amount"] == "5400.00"
        assert data["from_currency_code"] == "EUR"
        assert data["to_currency_code"] == "EGP"


@pytest.mark.asyncio
async def test_historical_rate_and_precision_rounding(db_session: AsyncSession):
    """Verify historical date lookup and 3-decimal/0-decimal ISO currency precision."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Hist Co", code=f"HST_{comp_id.hex[:4]}"))

        usd = Currency(company_id=comp_id, code="USD", name="US Dollar", symbol="$", decimal_places=2, is_base=True)
        kwd = Currency(company_id=comp_id, code="KWD", name="Kuwaiti Dinar", symbol="KD", decimal_places=3, is_base=False)
        jpy = Currency(company_id=comp_id, code="JPY", name="Japanese Yen", symbol="¥", decimal_places=0, is_base=False)
        db_session.add_all([usd, kwd, jpy])
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"hst_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Hist Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # KWD rate: 1 USD = 0.307123 KWD (3 decimals)
        await client.post(
            "/api/v1/fx_engine/rates",
            json={"from_currency_id": str(usd.id), "to_currency_id": str(kwd.id), "rate": "0.307123", "effective_date": "2026-01-01"},
            headers=headers,
        )

        # JPY rate: 1 USD = 152.678900 JPY (0 decimals)
        await client.post(
            "/api/v1/fx_engine/rates",
            json={"from_currency_id": str(usd.id), "to_currency_id": str(jpy.id), "rate": "152.678900", "effective_date": "2026-01-01"},
            headers=headers,
        )

        # 1. USD to KWD (100 * 0.307123 = 30.712)
        conv_kwd = await client.post(
            "/api/v1/fx_engine/convert",
            json={"amount": "100.00", "from_currency_id": str(usd.id), "to_currency_id": str(kwd.id)},
            headers=headers,
        )
        assert conv_kwd.status_code == 200
        assert conv_kwd.json()["converted_amount"] == "30.712"

        # 2. USD to JPY (100 * 152.6789 = 15268 rounded to 0 decimals)
        conv_jpy = await client.post(
            "/api/v1/fx_engine/convert",
            json={"amount": "100.00", "from_currency_id": str(usd.id), "to_currency_id": str(jpy.id)},
            headers=headers,
        )
        assert conv_jpy.status_code == 200
        assert conv_jpy.json()["converted_amount"] == "15268"

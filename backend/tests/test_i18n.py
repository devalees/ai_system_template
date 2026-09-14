"""Automated test suite for Multi-Language & Localization Module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.i18n.service import I18nService
from modules.base.i18n.models import TranslationTerm


def test_i18n_bilingual_field_resolution():
    """Verify dynamic resolution of JSONB multi-lingual fields."""
    bilingual_data = {"en": "Customer Invoice", "ar": "فاتورة العميل"}

    # Arabic resolution
    assert I18nService.resolve_field(bilingual_data, "ar") == "فاتورة العميل"

    # English resolution
    assert I18nService.resolve_field(bilingual_data, "en") == "Customer Invoice"

    # Fallback to English when French requested
    assert I18nService.resolve_field(bilingual_data, "fr") == "Customer Invoice"

    # String passthrough
    assert I18nService.resolve_field("Raw String", "ar") == "Raw String"


@pytest.mark.asyncio
async def test_i18n_translation_catalog_and_tenant_custom_terms(db_session: AsyncSession):
    """Verify catalog compilation from system defaults and tenant custom overrides."""
    company_id = uuid.uuid4()

    # 1. Initial catalog for Arabic
    cat = await I18nService.get_catalog(db=db_session, target_locale="ar", company_id=company_id)
    assert cat.locale == "ar"
    assert cat.direction == "rtl"
    assert cat.terms["Save"] == "حفظ"
    assert cat.terms["Cancel"] == "إلغاء"

    # 2. Add custom tenant term
    term = TranslationTerm(
        company_id=company_id,
        source_text="Shipment",
        module_name="logistics",
        translations={"en": "Shipment", "ar": "الشحنة"},
    )
    db_session.add(term)
    await db_session.commit()

    # 3. Verify translated term
    trans = await I18nService.translate_term(
        db=db_session,
        source_text="Shipment",
        target_locale="ar",
        company_id=company_id,
    )
    assert trans == "الشحنة"

    # 4. Verify catalog now contains custom term
    cat_updated = await I18nService.get_catalog(
        db=db_session, target_locale="ar", company_id=company_id
    )
    assert cat_updated.terms["Shipment"] == "الشحنة"


@pytest.mark.asyncio
async def test_i18n_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify REST API routes for locales, catalog, terms, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant A
        company_a = uuid.uuid4()
        user_a = f"i18n_a_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@example.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Admin Tenant A",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        token_a = login_a.json()["access_token"]
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "X-Company-ID": str(company_a),
        }

        # 2. Register Tenant B
        company_b = uuid.uuid4()
        user_b = f"i18n_b_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@example.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Admin Tenant B",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        token_b = login_b.json()["access_token"]
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Company-ID": str(company_b),
        }

        # 3. Check locales endpoint (public/shared)
        locales_res = await client.get("/api/v1/i18n/locales")
        assert locales_res.status_code == 200
        locales = locales_res.json()
        assert any(loc["code"] == "ar" and loc["direction"] == "rtl" for loc in locales)
        assert any(loc["code"] == "en" and loc["direction"] == "ltr" for loc in locales)

        # 4. Check Accept-Language resolution in catalog
        headers_a_ar = {**headers_a, "Accept-Language": "ar-SA,ar;q=0.9"}
        cat_res = await client.get("/api/v1/i18n/catalog", headers=headers_a_ar)
        assert cat_res.status_code == 200
        assert cat_res.json()["locale"] == "ar"
        assert cat_res.json()["direction"] == "rtl"
        assert cat_res.json()["terms"]["Save"] == "حفظ"

        # 5. Tenant A creates custom term
        term_res = await client.post(
            "/api/v1/i18n/terms",
            headers=headers_a,
            json={
                "source_text": "Warehouse",
                "module_name": "inventory",
                "translations": {"en": "Warehouse", "ar": "المستودع"},
            },
        )
        assert term_res.status_code == 201
        term_id = term_res.json()["id"]

        # 6. Tenant A translates text
        trans_res = await client.post(
            "/api/v1/i18n/translate",
            headers=headers_a,
            json={"text": "Warehouse", "target_locale": "ar"},
        )
        assert trans_res.status_code == 200
        assert trans_res.json()["translated_text"] == "المستودع"

        # 7. Tenant B Isolation: Tenant B does NOT see Tenant A's custom term
        b_terms = await client.get("/api/v1/i18n/terms", headers=headers_b)
        assert b_terms.status_code == 200
        assert len(b_terms.json()) == 0

        b_get_term = await client.get(f"/api/v1/i18n/terms/{term_id}", headers=headers_b)
        assert b_get_term.status_code == 404

"""Automated test suite for Multi-Tenant Settings Engine & Redis caching."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.settings.service import SettingsService


@pytest.mark.asyncio
async def test_settings_service_direct_crud_and_cache(db_session: AsyncSession):
    """Test SettingsService direct get, update, and Redis caching behavior."""
    company_id = uuid.uuid4()
    module_name = "test_module"

    # Initial get -> empty dict
    initial_settings = await SettingsService.get_settings(db_session, module_name, company_id)
    assert initial_settings == {}

    # Update settings
    updated = await SettingsService.update_settings(
        db_session,
        module_name,
        company_id,
        {"feature_flag_x": True, "limit": 100},
    )
    assert updated["feature_flag_x"] is True
    assert updated["limit"] == 100

    # Fetch settings (from DB or Redis cache)
    fetched = await SettingsService.get_settings(db_session, module_name, company_id)
    assert fetched == {"feature_flag_x": True, "limit": 100}

    # Partial merge update
    merged = await SettingsService.update_settings(
        db_session,
        module_name,
        company_id,
        {"limit": 250, "theme": "dark"},
    )
    assert merged["feature_flag_x"] is True
    assert merged["limit"] == 250
    assert merged["theme"] == "dark"


@pytest.mark.asyncio
async def test_settings_api_endpoints_and_multitenancy(db_session: AsyncSession):
    """Verify HTTP endpoints for settings and strict multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant A user
        user_a = f"tenant_a_{uuid.uuid4().hex[:6]}"
        company_a = uuid.uuid4()
        reg_a = await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@companya.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Tenant A User",
                "company_id": str(company_a),
            },
        )
        assert reg_a.status_code == 201
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Register Tenant B user
        user_b = f"tenant_b_{uuid.uuid4().hex[:6]}"
        company_b = uuid.uuid4()
        reg_b = await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@companyb.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Tenant B User",
                "company_id": str(company_b),
            },
        )
        assert reg_b.status_code == 201
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. Tenant A updates inventory settings
        res_patch_a = await client.patch(
            "/api/v1/settings/inventory",
            headers=headers_a,
            json={"settings_data": {"reorder_point": 10, "auto_notify": True}},
        )
        assert res_patch_a.status_code == 200
        assert res_patch_a.json()["reorder_point"] == 10

        # 4. Tenant B updates same module with different settings
        res_patch_b = await client.patch(
            "/api/v1/settings/inventory",
            headers=headers_b,
            json={"settings_data": {"reorder_point": 50, "auto_notify": False, "warehouse_code": "WH-B"}},
        )
        assert res_patch_b.status_code == 200
        assert res_patch_b.json()["reorder_point"] == 50

        # 5. Tenant A reads inventory settings -> isolated
        res_get_a = await client.get("/api/v1/settings/inventory", headers=headers_a)
        assert res_get_a.status_code == 200
        data_a = res_get_a.json()
        assert data_a["reorder_point"] == 10
        assert "warehouse_code" not in data_a

        # 6. Tenant B reads inventory settings -> isolated
        res_get_b = await client.get("/api/v1/settings/inventory", headers=headers_b)
        assert res_get_b.status_code == 200
        data_b = res_get_b.json()
        assert data_b["reorder_point"] == 50
        assert data_b["warehouse_code"] == "WH-B"

        # 7. List company settings endpoint
        res_list_a = await client.get("/api/v1/settings/", headers=headers_a)
        assert res_list_a.status_code == 200
        settings_list = res_list_a.json()
        assert len(settings_list) >= 1
        assert any(s["module_name"] == "inventory" for s in settings_list)

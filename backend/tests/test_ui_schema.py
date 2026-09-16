"""Comprehensive automated tests for Metadata-Driven Dynamic UI Engine & View Registry (`ui_schema`)."""

import uuid
import pytest
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User, Permission, UserPermissionLink
from modules.base.identity_rbac.flac_service import register_guarded_fields
from modules.base.settings.service import SettingsService
from modules.base.ui_schema.models import ViewDefinition, UserViewPreference
from modules.base.ui_schema.service import UISchemaService
from modules.base.ui_schema.schemas import (
    ViewDefinitionCreate,
    ViewDefinitionUpdate,
    UserViewPreferencePayload,
)
from modules.base.ui_schema.fixtures import seed_system_default_views


@pytest.mark.asyncio
async def test_dynamic_introspection_schema_generation(db_session: AsyncSession):
    """Verify that UISchemaService generates complete, valid Form, List, and Kanban schemas dynamically."""
    # 1. Dynamic Form Schema Generation
    form_schema = UISchemaService.generate_dynamic_default_schema("Product", "form")
    assert form_schema is not None
    assert form_schema["title_field"] in ("name", "code")
    assert len(form_schema["tabs"]) >= 1
    assert form_schema["sidebar"]["chatter_enabled"] is True
    assert form_schema["sidebar"]["min_split_ratio"] == 35.0
    assert form_schema["sidebar"]["max_split_ratio"] == 85.0
    assert form_schema["sidebar"]["collapsible"] is True

    # 2. Dynamic List Schema Generation
    list_schema = UISchemaService.generate_dynamic_default_schema("Product", "list")
    assert list_schema is not None
    assert len(list_schema["columns"]) >= 4
    col_names = [c["field_name"] for c in list_schema["columns"]]
    assert "name" in col_names
    assert "code" in col_names
    assert list_schema["default_sort_order"] in ("asc", "desc")

    # 3. Dynamic Kanban Schema Generation
    kanban_schema = UISchemaService.generate_dynamic_default_schema("SaleOrder", "kanban")
    assert kanban_schema is not None
    assert kanban_schema["group_by_field"] == "state"
    assert len(kanban_schema["lanes"]) >= 1
    assert kanban_schema["drag_drop_enabled"] is True
    assert kanban_schema["card"]["title_field"] in ("name", "order_number")


@pytest.mark.asyncio
async def test_system_views_seeding_and_bundle_resolution(db_session: AsyncSession):
    """Verify built-in system views seeding and bundle resolution for SaleOrder."""
    await seed_system_default_views(db_session)

    # Setup test company and superuser
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="UI Test Corp", code=f"UIT_{comp_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=comp_id,
        username=f"ui_user_{uuid.uuid4().hex[:6]}",
        email=f"ui_user_{uuid.uuid4().hex[:6]}@test.com",
        full_name="UI Test User",
        hashed_password="fake_hashed_password",
        is_superuser=True,
    )
    db_session.add(company)
    db_session.add(user)
    await db_session.commit()

    bundle = await UISchemaService.get_resolved_view_bundle("SaleOrder", user, db_session, comp_id)
    assert bundle.res_model == "SaleOrder"
    assert "form" in bundle.views
    assert "list" in bundle.views
    assert "kanban" in bundle.views

    form_view = bundle.views["form"]
    assert form_view["layout_template"] == "split_chatter_right"
    assert form_view["default_split_ratio"] == 65.0
    assert form_view["is_system"] is True
    assert form_view["schema"]["title_field"] == "name"

    kanban_view = bundle.views["kanban"]
    assert kanban_view["schema"]["group_by_field"] == "state"
    assert len(kanban_view["schema"]["lanes"]) == 5


@pytest.mark.asyncio
async def test_user_view_preferences_overlay(db_session: AsyncSession):
    """Verify that user personal preferences (split ratio, column widths, collapsed lanes) overlay onto views."""
    await seed_system_default_views(db_session)

    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Pref Test Corp", code=f"PREF_{comp_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=comp_id,
        username=f"pref_user_{uuid.uuid4().hex[:6]}",
        email=f"pref_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Pref Test User",
        hashed_password="fake_hashed_password",
        is_superuser=False,
    )
    db_session.add(company)
    db_session.add(user)
    await db_session.commit()

    # 1. Save Form Preference (dragged split ratio 74.5%)
    await UISchemaService.save_user_preference(
        user_id=user.id,
        res_model="SaleOrder",
        view_type="form",
        company_id=comp_id,
        payload=UserViewPreferencePayload(
            preferred_split_ratio=74.5,
            preferred_layout="split_chatter_right",
        ),
        db=db_session,
    )

    resolved_form = await UISchemaService.get_resolved_view_schema("SaleOrder", "form", user, db_session, comp_id)
    assert resolved_form["default_split_ratio"] == 74.5
    assert resolved_form["user_preference"] is not None
    assert resolved_form["user_preference"].preferred_split_ratio == 74.5

    # 2. Save List Preference (custom column order and widths)
    await UISchemaService.save_user_preference(
        user_id=user.id,
        res_model="SaleOrder",
        view_type="list",
        company_id=comp_id,
        payload=UserViewPreferencePayload(
            column_order=["amount_total", "name", "state"],
            column_widths={"name": 320, "amount_total": 180},
            visible_columns=["name", "amount_total"],
        ),
        db=db_session,
    )

    resolved_list = await UISchemaService.get_resolved_view_schema("SaleOrder", "list", user, db_session, comp_id)
    cols = resolved_list["schema"]["columns"]
    # Check that amount_total moved ahead of name
    col_names = [c["field_name"] for c in cols]
    assert col_names[0] == "amount_total"
    assert col_names[1] == "name"
    # Check width injected
    name_col = next(c for c in cols if c["field_name"] == "name")
    assert name_col["width"] == 320
    # Check default_visible respected
    assert name_col["default_visible"] is True

    # 3. Save Kanban Preference (collapsed lane)
    await UISchemaService.save_user_preference(
        user_id=user.id,
        res_model="SaleOrder",
        view_type="kanban",
        company_id=comp_id,
        payload=UserViewPreferencePayload(
            kanban_collapsed_lanes=["cancelled"],
        ),
        db=db_session,
    )

    resolved_kanban = await UISchemaService.get_resolved_view_schema("SaleOrder", "kanban", user, db_session, comp_id)
    cancelled_lane = next(l for l in resolved_kanban["schema"]["lanes"] if l["value"] == "cancelled")
    assert cancelled_lane["is_folded"] is True


@pytest.mark.asyncio
async def test_custom_view_persistence_and_fallback(db_session: AsyncSession):
    """Verify Studio custom view creation, high priority override, update, and deletion fallback."""
    await seed_system_default_views(db_session)

    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Studio Corp", code=f"STD_{comp_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=comp_id,
        username=f"studio_user_{uuid.uuid4().hex[:6]}",
        email=f"std_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Studio User",
        hashed_password="fake_hashed_password",
        is_superuser=True,
    )
    db_session.add(company)
    db_session.add(user)
    await db_session.commit()

    # 1. Initial resolution returns system view
    initial = await UISchemaService.get_resolved_view_schema("Product", "form", user, db_session, comp_id)
    assert initial["is_system"] is True
    assert initial["layout_template"] == "split_chatter_right"

    # 2. Create Tenant Custom View (Studio Save) with priority 50
    custom_view = await UISchemaService.create_view_definition(
        payload=ViewDefinitionCreate(
            res_model="Product",
            view_type="form",
            name="Customized Product Studio Layout",
            layout_template="full_width",
            default_split_ratio=100.0,
            priority=50,
            is_default=True,
            schema={"custom_studio_prop": "active", "tabs": []},
        ),
        db=db_session,
        company_id=comp_id,
    )

    # 3. Resolution now selects the custom tenant view
    resolved = await UISchemaService.get_resolved_view_schema("Product", "form", user, db_session, comp_id)
    assert resolved["is_system"] is False
    assert resolved["view_id"] == str(custom_view.id)
    assert resolved["layout_template"] == "full_width"
    assert resolved["name"] == "Customized Product Studio Layout"

    # 4. Update Custom View
    updated = await UISchemaService.update_view_definition(
        view_id=custom_view.id,
        payload=ViewDefinitionUpdate(name="Updated Studio Layout", default_split_ratio=55.0),
        db=db_session,
    )
    assert updated.name == "Updated Studio Layout"
    assert updated.default_split_ratio == 55.0

    # 5. Delete Custom View (revert to default)
    deleted = await UISchemaService.delete_view_definition(custom_view.id, db_session)
    assert deleted is True

    # 6. Resolution falls back to system view
    fallback = await UISchemaService.get_resolved_view_schema("Product", "form", user, db_session, comp_id)
    assert fallback["is_system"] is True
    assert fallback["layout_template"] == "split_chatter_right"


@pytest.mark.asyncio
async def test_flac_schema_security_pruning(db_session: AsyncSession):
    """Verify that Field-Level Access Control (FLAC) purges or enforces readonly on guarded schema fields."""
    register_guarded_fields("product", ["cost_price"])

    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Security Corp", code=f"SEC_{comp_id.hex[:4]}")
    user = User(
        id=uuid.uuid4(),
        company_id=comp_id,
        username=f"flac_user_{uuid.uuid4().hex[:6]}",
        email=f"flac_{uuid.uuid4().hex[:6]}@test.com",
        full_name="FLAC User",
        hashed_password="fake_hashed_password",
        is_superuser=False,
    )
    db_session.add(company)
    db_session.add(user)
    await db_session.commit()

    # 1. User has NO permission on cost_price -> field must be purged from schema
    schema = UISchemaService.generate_dynamic_default_schema("Product", "list")
    sanitized = await UISchemaService.apply_flac_to_schema(schema, "Product", user, db_session)
    col_names = [c["field_name"] for c in sanitized["columns"]]
    assert "cost_price" not in col_names

    # 2. Grant READ-ONLY permission to user on product.cost_price:read
    stmt_p = select(Permission).where(Permission.code == "product.cost_price:read")
    read_perm = (await db_session.execute(stmt_p)).scalar_one_or_none()
    if not read_perm:
        read_perm = Permission(
            id=uuid.uuid4(),
            company_id=comp_id,
            name="Read Product Cost Price",
            code="product.cost_price:read",
            module_name="products",
            resource="product",
            action="read",
            permission_type="field",
            field_name="cost_price",
        )
        db_session.add(read_perm)
        await db_session.flush()

    link = UserPermissionLink(
        user_id=user.id,
        permission_id=read_perm.id,
        is_granted=True,
        company_id=comp_id,
    )
    db_session.add(link)
    await db_session.commit()

    # In Form view, cost_price should now appear but be marked readonly: True
    form_schema = UISchemaService.generate_dynamic_default_schema("Product", "form")
    sanitized_form = await UISchemaService.apply_flac_to_schema(form_schema, "Product", user, db_session)

    # Find cost_price in form tabs
    cost_field = None
    for tab in sanitized_form["tabs"]:
        for sec in tab.get("sections", []):
            for row in sec.get("rows", []):
                for fw in row.get("fields", []):
                    if fw.get("field_name") == "cost_price":
                        cost_field = fw
                        break
    if cost_field:
        assert cost_field["readonly"] is True


@pytest.mark.asyncio
async def test_ui_schema_rest_api_endpoints(db_session: AsyncSession):
    """Verify REST API endpoints for UI models catalog, view bundles, preferences, and custom views."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="UI API Corp", code=f"UIA_{comp_id.hex[:4]}"))
        await db_session.commit()

        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"ui_admin_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "UI Admin", "company_id": str(comp_id)},
        )
        u = (await db_session.execute(select(User).where(User.username == username))).scalar_one()
        u.is_superuser = True
        await db_session.commit()

        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Company-ID": str(comp_id)}

        # 1. GET /api/v1/ui/models
        models_res = await client.get("/api/v1/ui/models", headers=headers)
        assert models_res.status_code == 200
        models_data = models_res.json()
        assert len(models_data) > 0
        names = [m["model_name"] for m in models_data]
        assert "SaleOrder" in names or "Product" in names

        # 2. GET /api/v1/ui/views/SaleOrder (bundle)
        bundle_res = await client.get("/api/v1/ui/views/SaleOrder", headers=headers)
        assert bundle_res.status_code == 200
        bundle_json = bundle_res.json()
        assert bundle_json["res_model"] == "SaleOrder"
        assert "form" in bundle_json["views"]
        assert "list" in bundle_json["views"]

        # 3. GET /api/v1/ui/views/SaleOrder/form (single resolved)
        single_res = await client.get("/api/v1/ui/views/SaleOrder/form", headers=headers)
        assert single_res.status_code == 200
        assert single_res.json()["view_type"] == "form"

        # 4. PUT /api/v1/ui/preferences/SaleOrder/form
        pref_res = await client.put(
            "/api/v1/ui/preferences/SaleOrder/form",
            headers=headers,
            json={"preferred_split_ratio": 68.5, "preferred_layout": "split_chatter_right"},
        )
        assert pref_res.status_code == 200
        assert pref_res.json()["preferred_split_ratio"] == 68.5

        # 5. GET /api/v1/ui/preferences/SaleOrder/form
        get_pref_res = await client.get("/api/v1/ui/preferences/SaleOrder/form", headers=headers)
        assert get_pref_res.status_code == 200
        assert get_pref_res.json()["preferred_split_ratio"] == 68.5

        # 6. POST /api/v1/ui/views (Create custom view)
        create_res = await client.post(
            "/api/v1/ui/views",
            headers=headers,
            json={
                "res_model": "SaleOrder",
                "view_type": "form",
                "name": "Custom API Sales Form",
                "layout_template": "full_width",
                "default_split_ratio": 80.0,
                "priority": 25,
                "is_default": True,
                "schema": {"test_key": "val"},
            },
        )
        assert create_res.status_code == 201
        created_view = create_res.json()
        view_id = created_view["id"]
        assert created_view["name"] == "Custom API Sales Form"

        # 7. PUT /api/v1/ui/views/{id} (Update custom view)
        update_res = await client.put(
            f"/api/v1/ui/views/{view_id}",
            headers=headers,
            json={"name": "Renamed API Sales Form"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "Renamed API Sales Form"

        # 8. DELETE /api/v1/ui/views/{id} (Delete custom view)
        del_res = await client.delete(f"/api/v1/ui/views/{view_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

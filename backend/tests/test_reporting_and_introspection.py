"""Automated test suite for TCA Introspection, Pre-Flight Validation, and Universal Headless Reporting Engine."""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company, User
from modules.base.settings.service import SettingsService
from modules.base.documents.models import DocumentAttachment
from modules.base.reporting.models import ReportTemplate, ReportDefinition
from modules.base.reporting.registry import report_registry
from modules.base.automated_actions.engine.registry import action_registry
from modules.base.automated_actions.handlers.base import ActionContext
from modules.base.reporting.action_handler import GenerateReportActionHandler, GenerateReportActionConfig
from modules.base.reporting.fixtures import seed_default_report_templates


@pytest.mark.asyncio
async def test_model_and_field_introspection(db_session: AsyncSession):
    """Verify ORM model catalog and granular field introspection endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test company & user
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Intro Test Co", code=f"INTRO_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"intro_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Models Introspection
        res = await client.get("/api/v1/automated_actions/introspection/models", headers=headers)
        assert res.status_code == 200
        models = res.json()
        assert len(models) >= 15
        model_names = {m["model_name"] for m in models}
        assert "User" in model_names
        assert "DocumentAttachment" in model_names
        assert "AutomatedAction" in model_names

        # 2. User Field Introspection
        res_fields = await client.get("/api/v1/automated_actions/introspection/models/User/fields", headers=headers)
        assert res_fields.status_code == 200
        user_spec = res_fields.json()
        assert user_spec["model_name"] == "User"
        field_map = {f["name"]: f for f in user_spec["fields"]}
        assert "username" in field_map
        assert field_map["username"]["type"] == "string"
        assert field_map["username"]["required"] is True
        assert field_map["id"]["read_only"] is True

        # 3. Non-existent model returns 404
        res_404 = await client.get("/api/v1/automated_actions/introspection/models/NonExistentEntity/fields", headers=headers)
        assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_automated_actions_preflight_validation(db_session: AsyncSession):
    """Verify pre-flight schema validation prevents invalid record mutations in rules."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Val Co", code=f"VAL_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"val_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Reject create_record with non-existent target model
        res_bad_model = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers,
            json={
                "name": "Invalid Model Rule",
                "target_model": "User",
                "trigger_type": "on_create",
                "action_type": "create_record",
                "action_config": {
                    "model_name": "FakeGhostModel",
                    "values": {"name": "Test"},
                },
            },
        )
        assert res_bad_model.status_code == 422

        # 2. Reject create_record with missing required field
        res_missing_req = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers,
            json={
                "name": "Missing Required Field Rule",
                "target_model": "User",
                "trigger_type": "on_create",
                "action_type": "create_record",
                "action_config": {
                    "model_name": "DocumentAttachment",
                    "values": {"description": "Missing name and file_hash"},
                },
            },
        )
        assert res_missing_req.status_code == 422

        # 3. Reject update_record with invalid field
        res_bad_field = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers,
            json={
                "name": "Bad Field Update Rule",
                "target_model": "User",
                "trigger_type": "on_update",
                "action_type": "update_record",
                "action_config": {
                    "fields": {"non_existent_column_xyz": "value"},
                },
            },
        )
        assert res_bad_field.status_code == 422

        # 4. Reject update_record targeting read-only primary key
        res_read_only = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers,
            json={
                "name": "Read Only Update Rule",
                "target_model": "User",
                "trigger_type": "on_update",
                "action_type": "update_record",
                "action_config": {
                    "fields": {"id": str(uuid.uuid4())},
                },
            },
        )
        assert res_read_only.status_code == 422

        # 5. Successful rule creation with valid fields
        res_valid = await client.post(
            "/api/v1/automated_actions/rules",
            headers=headers,
            json={
                "name": "Valid Update Record Rule",
                "target_model": "User",
                "trigger_type": "on_update",
                "action_type": "update_record",
                "action_config": {
                    "fields": {"full_name": "Updated by Automation"},
                },
            },
        )
        assert res_valid.status_code == 201


@pytest.mark.asyncio
async def test_reporting_catalog_and_templates(db_session: AsyncSession):
    """Verify report catalog retrieval and ReportTemplate CRUD lifecycle."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Report Test Co", code=f"REP_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})
        await seed_default_report_templates(db_session)

        username = f"rep_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Check Catalog
        cat_res = await client.get("/api/v1/reporting/catalog", headers=headers)
        assert cat_res.status_code == 200
        catalog = cat_res.json()
        report_codes = {r["code"] for r in catalog}
        assert "documents.storage_audit" in report_codes
        assert "identity.user_directory" in report_codes

        # 2. List Templates (verify seeded standard_clean)
        tpl_res = await client.get("/api/v1/reporting/templates", headers=headers)
        assert tpl_res.status_code == 200
        templates = tpl_res.json()
        assert len(templates) >= 1
        assert any(t["code"] == "standard_clean" for t in templates)

        # 3. Create Custom Template
        create_tpl = await client.post(
            "/api/v1/reporting/templates",
            headers=headers,
            json={
                "name": "Custom Invoice Layout",
                "code": "invoice_modern",
                "orientation": "portrait",
                "primary_color": "#0D9488",
                "header_text": "Commercial Invoice Header",
                "footer_text": "Payment terms: 30 days net",
                "is_default": False,
            },
        )
        assert create_tpl.status_code == 201
        tpl_data = create_tpl.json()
        tpl_id = tpl_data["id"]

        # 4. Patch Template
        patch_tpl = await client.patch(
            f"/api/v1/reporting/templates/{tpl_id}",
            headers=headers,
            json={"header_text": "Updated Header Text"},
        )
        assert patch_tpl.status_code == 200
        assert patch_tpl.json()["header_text"] == "Updated Header Text"

        # 5. Delete Template
        del_tpl = await client.delete(f"/api/v1/reporting/templates/{tpl_id}", headers=headers)
        assert del_tpl.status_code == 204


@pytest.mark.asyncio
async def test_report_data_and_multi_format_rendering(db_session: AsyncSession):
    """Verify execution of reports across JSON, CSV, Excel, and PDF formats."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Format Co", code=f"FMT_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"fmt_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Format Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Pure Data JSON Mode
        data_res = await client.post("/api/v1/reporting/identity.user_directory/data", headers=headers, json={})
        assert data_res.status_code == 200
        res_json = data_res.json()
        assert res_json["report_code"] == "identity.user_directory"
        assert len(res_json["columns"]) == 7
        assert res_json["total_rows"] >= 1
        assert "total_users" in res_json["aggregates"]
        assert res_json["company_info"]["name"] == "Format Co"

        # 2. Export CSV Mode
        csv_res = await client.post(
            "/api/v1/reporting/identity.user_directory/export",
            headers=headers,
            json={"format": "csv"},
        )
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        csv_content = csv_res.content
        assert csv_content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        assert b"Username" in csv_content

        # 3. Export Excel Mode
        xlsx_res = await client.post(
            "/api/v1/reporting/identity.user_directory/export",
            headers=headers,
            json={"format": "xlsx"},
        )
        assert xlsx_res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in xlsx_res.headers.get("content-type", "")
        assert xlsx_res.content.startswith(b"PK\x03\x04")  # Zip/XLSX magic bytes

        # 4. Export PDF Mode
        pdf_res = await client.post(
            "/api/v1/reporting/identity.user_directory/export",
            headers=headers,
            json={"format": "pdf"},
        )
        assert pdf_res.status_code == 200
        assert "application/pdf" in pdf_res.headers.get("content-type", "")
        assert pdf_res.content.startswith(b"%PDF-")  # PDF magic bytes

        # 5. Export and Save to DocumentAttachment
        save_res = await client.post(
            "/api/v1/reporting/identity.user_directory/export",
            headers=headers,
            json={"format": "pdf", "save_to_documents": True},
        )
        assert save_res.status_code == 200
        attach_meta = save_res.json()
        assert attach_meta["status"] == "attached"
        assert "attachment_id" in attach_meta
        assert attach_meta["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_dynamic_report_builder_and_crud(db_session: AsyncSession):
    """Verify dynamic report definitions CRUD and ad-hoc aggregation query execution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comp_id = uuid.uuid4()
        db_session.add(Company(id=comp_id, name="Dyn Co", code=f"DYN_{comp_id.hex[:4]}"))
        await db_session.commit()
        await SettingsService.update_settings(db_session, "identity_rbac", comp_id, {"allow_registration": True})

        username = f"dyn_user_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={"email": f"{username}@test.com", "username": username, "password": "Password123!", "full_name": "Dyn Tester", "company_id": str(comp_id)},
        )
        login_res = await client.post("/api/v1/identity_rbac/auth/login", json={"identifier": username, "password": "Password123!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 1. Create Dynamic Report Definition on User grouped by is_active
        def_code = f"dyn_users_{uuid.uuid4().hex[:4]}"
        create_def = await client.post(
            "/api/v1/reporting/definitions",
            headers=headers,
            json={
                "name": "Users Grouped By Active Status",
                "code": def_code,
                "target_model": "User",
                "group_by": ["is_active"],
                "aggregations": {"id": "count"},
            },
        )
        assert create_def.status_code == 201
        def_id = create_def.json()["id"]

        # 2. Run Dynamic Report
        run_res = await client.post(f"/api/v1/reporting/{def_code}/data", headers=headers, json={})
        assert run_res.status_code == 200
        dyn_data = run_res.json()
        assert dyn_data["report_code"] == f"dynamic.user"
        assert any(c["name"] == "is_active" for c in dyn_data["columns"])
        assert any(c["name"] == "id_count" for c in dyn_data["columns"])
        assert dyn_data["total_rows"] >= 1

        # 3. Soft Delete Definition
        del_res = await client.delete(f"/api/v1/reporting/definitions/{def_id}", headers=headers)
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_tca_generate_report_action_handler(db_session: AsyncSession):
    """Verify GenerateReportActionHandler execution via TCA engine attaches document to record."""
    comp_id = uuid.uuid4()
    company = Company(id=comp_id, name="Action Report Co", code=f"ACT_{comp_id.hex[:4]}")
    uid = uuid.uuid4().hex[:6]
    user = User(id=uuid.uuid4(), company_id=comp_id, email=f"act_tester_{uid}@test.com", username=f"act_tester_{uid}", full_name="Action Tester", hashed_password="pw")
    db_session.add_all([company, user])
    await db_session.commit()

    handler = action_registry.get("generate_report")
    assert handler is not None
    assert isinstance(handler, GenerateReportActionHandler)

    context = ActionContext(
        company_id=comp_id,
        user_id=user.id,
        target_model="User",
        target_id=user.id,
        record=user,
        record_data={"id": str(user.id), "username": user.username, "email": user.email},
        trigger_type="on_create",
    )

    config = GenerateReportActionConfig(
        report_code="identity.user_directory",
        format="pdf",
        attach_to_record=True,
        send_email=False,
    )

    result = await handler.execute(db=db_session, context=context, config=config)
    assert result["status"] == "generated"
    assert result["report_code"] == "identity.user_directory"
    assert "attachment" in result
    assert result["attachment"]["status"] == "attached"
    assert result["attachment"]["res_model"].lower() == "user"
    assert result["attachment"]["res_id"] == str(user.id)

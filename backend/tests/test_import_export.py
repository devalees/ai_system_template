"""Automated test suite for Universal Streaming Import & Export Module."""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.lookups.models import Tag
from modules.base.import_export.processor import DataProcessor
from modules.base.import_export.service import ImportExportService
from modules.base.import_export.schemas import ExportRequest


def test_data_processor_formats():
    """Verify parsing and generating CSV, Excel, and JSON data formats."""
    rows = [
        {"name": "VIP Customer", "color": "#ff0000"},
        {"name": "Wholesale", "color": "#00ff00"},
    ]

    # 1. CSV
    csv_bytes = DataProcessor.generate_csv(rows)
    parsed_csv = DataProcessor.parse_csv(csv_bytes)
    assert len(parsed_csv) == 2
    assert parsed_csv[0]["name"] == "VIP Customer"
    assert parsed_csv[1]["color"] == "#00ff00"

    # 2. Excel (openpyxl)
    excel_bytes = DataProcessor.generate_excel(rows)
    parsed_excel = DataProcessor.parse_excel(excel_bytes)
    assert len(parsed_excel) == 2
    assert parsed_excel[0]["name"] == "VIP Customer"
    assert parsed_excel[1]["color"] == "#00ff00"

    # 3. JSON
    json_bytes = DataProcessor.generate_json(rows)
    parsed_json = DataProcessor.parse_json(json_bytes)
    assert len(parsed_json) == 2
    assert parsed_json[0]["name"] == "VIP Customer"


@pytest.mark.asyncio
async def test_import_and_export_service_synchronous(db_session: AsyncSession):
    """Verify bulk entity import and export service execution."""
    company_id = uuid.uuid4()

    # 1. Import CSV into Tag model
    csv_content = b"Tag_Name,Tag_Color\nGold Partner,#ffd700\nSilver Partner,#c0c0c0\n"
    mapping = {"Tag_Name": "name", "Tag_Color": "color"}

    job = await ImportExportService.create_import_job(
        db=db_session,
        content=csv_content,
        file_name="tags.csv",
        file_format="csv",
        model_name="lookups.tag",
        field_mapping=mapping,
        company_id=company_id,
        async_run=False,
    )

    assert job.status == "completed"
    assert job.total_records == 2
    assert job.processed_records == 2
    assert job.failed_records == 0

    # Verify rows exist in DB
    tag_stmt = select(Tag).where(Tag.company_id == company_id)
    tags = (await db_session.execute(tag_stmt)).scalars().all()
    assert len(tags) == 2
    tag_names = [t.name for t in tags]
    assert "Gold Partner" in tag_names
    assert "Silver Partner" in tag_names

    # 2. Export Tags to CSV
    export_req = ExportRequest(
        model_name="lookups.tag",
        file_format="csv",
        fields=["name", "color"],
        async_job=False,
    )
    export_job = await ImportExportService.create_export_job(
        db=db_session,
        req=export_req,
        company_id=company_id,
    )

    assert export_job.status == "completed"
    assert export_job.total_records == 2
    assert export_job.file_size > 0


@pytest.mark.asyncio
async def test_import_export_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify REST API import, export job polling, file download, and tenant boundary enforcement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}", allow_registration=True),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}", allow_registration=True),
        ])
        await db_session.commit()

        # 1. Setup Tenant A
        user_a = f"impexp_a_{uuid.uuid4().hex[:6]}"
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

        # 2. Setup Tenant B
        user_b = f"impexp_b_{uuid.uuid4().hex[:6]}"
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

        # 3. Tenant A uploads CSV import
        csv_file = ("test_tags.csv", io.BytesIO(b"name,color\nImportedTagA,#112233\n"), "text/csv")
        import_res = await client.post(
            "/api/v1/import_export/import",
            headers=headers_a,
            files={"file": csv_file},
            data={"model_name": "lookups.tag", "async_job": "false"},
        )
        assert import_res.status_code == 202
        import_job_id = import_res.json()["job_id"]

        # 4. Tenant A checks import job status
        job_res = await client.get(f"/api/v1/import_export/jobs/{import_job_id}", headers=headers_a)
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "completed"
        assert job_res.json()["processed_records"] == 1

        # 5. Tenant A requests export
        export_res = await client.post(
            "/api/v1/import_export/export",
            headers=headers_a,
            json={
                "model_name": "lookups.tag",
                "file_format": "csv",
                "fields": ["name", "color"],
                "async_job": False,
            },
        )
        assert export_res.status_code == 202
        export_job_id = export_res.json()["job_id"]

        # 6. Tenant A downloads exported CSV
        download_res = await client.get(
            f"/api/v1/import_export/jobs/{export_job_id}/download",
            headers=headers_a,
        )
        assert download_res.status_code == 200
        assert "text/csv" in download_res.headers["content-type"]
        assert b"ImportedTagA" in download_res.content

        # 7. Tenant B Isolation verification
        # Tenant B has 0 jobs
        b_jobs = await client.get("/api/v1/import_export/jobs", headers=headers_b)
        assert b_jobs.status_code == 200
        assert len(b_jobs.json()) == 0

        # Tenant B cannot inspect Tenant A's job
        b_get_job = await client.get(f"/api/v1/import_export/jobs/{import_job_id}", headers=headers_b)
        assert b_get_job.status_code == 404

        # Tenant B cannot download Tenant A's export
        b_download = await client.get(
            f"/api/v1/import_export/jobs/{export_job_id}/download",
            headers=headers_b,
        )
        assert b_download.status_code == 404

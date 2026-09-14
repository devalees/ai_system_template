"""Automated test suite for Unified Atomic Backup & Archive Engine."""

import os
import uuid
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.identity_rbac.models import Company
from modules.base.backup.engine import BackupEngine
from modules.base.backup.service import BackupService
from modules.base.lookups.models import Tag


def test_backup_engine_archive_creation_and_verification():
    """Verify BackupEngine packs tar.gz archives and verifies cryptographic integrity."""
    output_path = "/tmp/test_backup_archive.tar.gz"
    sql_dump = "CREATE TABLE sample (id INT);\nINSERT INTO sample VALUES (1);\n"
    manifest = {"app": "sovereign", "version": "1.0.0"}

    size, checksum = BackupEngine.create_tar_archive(
        output_path=output_path,
        sql_dump=sql_dump,
        filestore_files=[],
        manifest_data=manifest,
    )

    assert size > 0
    assert len(checksum) == 64

    # Verify archive
    verification = BackupEngine.verify_archive(output_path)
    assert verification["valid"] is True
    assert verification["checksum_sha256"] == checksum
    assert verification["manifest"]["app"] == "sovereign"

    if os.path.exists(output_path):
        os.remove(output_path)


@pytest.mark.asyncio
async def test_backup_service_synchronous(db_session: AsyncSession):
    """Verify BackupService extracts database state and produces complete bundle."""
    company_id = uuid.uuid4()

    # Seed test data for tenant
    tag = Tag(company_id=company_id, name="Test Backup Tag", color="#abcdef")
    db_session.add(tag)
    await db_session.commit()

    record = await BackupService.create_backup(
        db=db_session,
        company_id=company_id,
        backup_type="full",
        includes_filestore=False,
        async_run=False,
    )

    assert record.id is not None
    assert record.status == "completed"
    assert record.file_size > 0
    assert len(record.checksum_sha256) == 64

    # Verify through service
    res = BackupService.verify_backup_record(record)
    assert res["valid"] is True

    # Cleanup file
    if os.path.exists(record.storage_path):
        os.remove(record.storage_path)


@pytest.mark.asyncio
async def test_backup_api_endpoints_and_tenant_isolation(db_session: AsyncSession):
    """Verify REST API backup triggers, downloads, verification, and multi-tenant isolation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed test companies
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        db_session.add_all([
            Company(id=company_a, name="Company A", code=f"CA_{company_a.hex[:4]}", allow_registration=True),
            Company(id=company_b, name="Company B", code=f"CB_{company_b.hex[:4]}", allow_registration=True),
        ])
        await db_session.commit()

        # 1. Register Tenant A
        user_a = f"backup_a_{uuid.uuid4().hex[:6]}"
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
        user_b = f"backup_b_{uuid.uuid4().hex[:6]}"
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

        # 3. Tenant A triggers backup synchronously
        create_res = await client.post(
            "/api/v1/backup/create",
            headers=headers_a,
            json={
                "backup_type": "full",
                "includes_filestore": False,
                "async_run": False,
            },
        )
        assert create_res.status_code == 202
        backup_id = create_res.json()["backup_id"]

        # 4. Tenant A checks backup details
        details_res = await client.get(f"/api/v1/backup/{backup_id}", headers=headers_a)
        assert details_res.status_code == 200
        assert details_res.json()["status"] == "completed"
        assert details_res.json()["file_size"] > 0

        # 5. Tenant A downloads archive
        dl_res = await client.get(f"/api/v1/backup/{backup_id}/download", headers=headers_a)
        assert dl_res.status_code == 200
        assert "application/gzip" in dl_res.headers["content-type"]
        # Check gzip magic header (0x1f 0x8b)
        assert dl_res.content[:2] == b"\x1f\x8b"

        # 6. Tenant A verifies archive
        verify_res = await client.post(f"/api/v1/backup/{backup_id}/verify", headers=headers_a)
        assert verify_res.status_code == 200
        assert verify_res.json()["valid"] is True

        # 7. Tenant B isolation verification
        # Tenant B has 0 backups
        b_list = await client.get("/api/v1/backup/list", headers=headers_b)
        assert b_list.status_code == 200
        assert len(b_list.json()) == 0

        # Tenant B cannot inspect Tenant A's backup
        b_details = await client.get(f"/api/v1/backup/{backup_id}", headers=headers_b)
        assert b_details.status_code == 404

        # Tenant B cannot download Tenant A's backup
        b_dl = await client.get(f"/api/v1/backup/{backup_id}/download", headers=headers_b)
        assert b_dl.status_code == 404

        # Tenant B cannot delete Tenant A's backup
        b_del = await client.delete(f"/api/v1/backup/{backup_id}", headers=headers_b)
        assert b_del.status_code == 404

        # 8. Tenant A deletes backup
        del_res = await client.delete(f"/api/v1/backup/{backup_id}", headers=headers_a)
        assert del_res.status_code == 204

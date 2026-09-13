"""Automated test suite for Document & Content-Addressable Storage module."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from modules.base.documents.service import DocumentService
from modules.base.documents.storage import StorageEngine


@pytest.mark.asyncio
async def test_document_storage_cas_and_deduplication(db_session: AsyncSession):
    """Verify Content-Addressable Storage (CAS) generates SHA-256 digests and deduplicates blobs."""
    company_id = uuid.uuid4()
    content = b"Sovereign Enterprise Confidential Contract Content 2026"

    # 1. First upload
    doc1 = await DocumentService.create_attachment(
        db=db_session,
        name="contract_v1.pdf",
        content=content,
        mime_type="application/pdf",
        company_id=company_id,
        res_model="contract",
        res_id=uuid.uuid4(),
    )
    assert doc1.id is not None
    assert doc1.file_size == len(content)

    # 2. Upload identical content under a different filename
    doc2 = await DocumentService.create_attachment(
        db=db_session,
        name="contract_copy.pdf",
        content=content,
        mime_type="application/pdf",
        company_id=company_id,
        res_model="contract",
        res_id=uuid.uuid4(),
    )

    # Both records share the exact same hash and relative storage path (deduplication)
    assert doc1.file_hash == doc2.file_hash
    assert doc1.storage_path == doc2.storage_path

    # Read blob back
    read_bytes = await StorageEngine.read_blob(doc1.storage_path)
    assert read_bytes == content


@pytest.mark.asyncio
async def test_document_endpoints_and_multitenancy(db_session: AsyncSession):
    """Verify HTTP upload, binary streaming download, and multi-tenant security."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant A
        user_a = f"doc_a_{uuid.uuid4().hex[:6]}"
        company_a = uuid.uuid4()
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_a}@test.com",
                "username": user_a,
                "password": "Password123!",
                "full_name": "Tenant A Document Manager",
                "company_id": str(company_a),
            },
        )
        login_a = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_a, "password": "Password123!"},
        )
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # 2. Register Tenant B
        user_b = f"doc_b_{uuid.uuid4().hex[:6]}"
        company_b = uuid.uuid4()
        await client.post(
            "/api/v1/identity_rbac/auth/register",
            json={
                "email": f"{user_b}@test.com",
                "username": user_b,
                "password": "Password123!",
                "full_name": "Tenant B Document Manager",
                "company_id": str(company_b),
            },
        )
        login_b = await client.post(
            "/api/v1/identity_rbac/auth/login",
            json={"identifier": user_b, "password": "Password123!"},
        )
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        test_bytes = b"%PDF-1.4 Sovereign Sample Invoice Document Data"
        res_entity_id = uuid.uuid4()

        # 3. Tenant A uploads attachment
        res_upload = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            data={"res_model": "invoice", "res_id": str(res_entity_id), "description": "Customer Invoice PDF"},
            files={"file": ("invoice_sample.pdf", test_bytes, "application/pdf")},
        )
        assert res_upload.status_code == 201
        doc_data = res_upload.json()
        doc_id = doc_data["id"]
        assert doc_data["name"] == "invoice_sample.pdf"
        assert doc_data["file_size"] == len(test_bytes)

        # 4. Tenant A downloads binary
        res_download = await client.get(f"/api/v1/documents/{doc_id}/download", headers=headers_a)
        assert res_download.status_code == 200
        assert res_download.content == test_bytes
        assert "invoice_sample.pdf" in res_download.headers.get("content-disposition", "")

        # 5. Tenant A lists entity attachments
        res_list = await client.get(f"/api/v1/documents/entity/invoice/{res_entity_id}", headers=headers_a)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        # 6. Tenant B attempts to access Tenant A's document -> 404
        res_b = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
        assert res_b.status_code == 404

        # 7. Soft delete attachment by Tenant A
        res_del = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert res_del.status_code == 204

        # 8. Subsequent access returns 404 (soft-deleted)
        res_after_del = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert res_after_del.status_code == 404

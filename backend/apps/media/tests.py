"""
Unit tests for Universal Document & Media Management models and helpers.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.media.models import Document, calculate_sha256, format_human_size
from apps.tenants.models import Organization

User = get_user_model()


class DocumentModelTests(TestCase):
    """Test suite verifying Document model, SHA-256 checksums, and Generic FK attachments."""

    def setUp(self):
        self.org = Organization.objects.create(name="Media Org", slug="media-org")
        self.user = User.objects.create_user(username="mediauser", password="password123")
        self.file_content = b"Hello, this is a test document content for SHA-256 calculation."
        self.test_file = SimpleUploadedFile(
            name="test_report.txt",
            content=self.file_content,
            content_type="text/plain"
        )

    def test_document_creation_and_auto_checksum(self):
        """Verify Document creation auto-calculates SHA-256 checksum, size, and MIME type."""
        doc = Document.objects.create(
            organization=self.org,
            file=self.test_file,
            filename="test_report.txt",
            uploaded_by=self.user,
        )
        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.file_size, len(self.file_content))
        self.assertEqual(len(doc.checksum_sha256), 64)
        self.assertIn("text/plain", doc.mime_type)
        self.assertEqual(doc.uploaded_by, self.user)
        self.assertIn("B", doc.file_size_human)

    def test_generic_foreign_key_attachment(self):
        """Verify attaching a Document to a target model instance via GenericForeignKey."""
        content_type = ContentType.objects.get_for_model(Organization)
        doc = Document.objects.create(
            organization=self.org,
            file=self.test_file,
            filename="org_policy.pdf",
            content_type=content_type,
            object_id=str(self.org.id)
        )
        doc.refresh_from_db()
        self.assertEqual(doc.content_object, self.org)
        self.assertEqual(doc.content_type, content_type)
        self.assertEqual(doc.object_id, str(self.org.id))

    def test_human_size_formatter(self):
        """Verify format_human_size utility."""
        self.assertEqual(format_human_size(500), "500 B")
        self.assertEqual(format_human_size(2048), "2.0 KB")
        self.assertEqual(format_human_size(5 * 1024 * 1024), "5.0 MB")
        self.assertEqual(format_human_size(3 * 1024 * 1024 * 1024), "3.0 GB")

    def test_document_soft_delete(self):
        """Verify Document inherits SoftDeleteModel capabilities."""
        doc = Document.objects.create(
            organization=self.org,
            file=self.test_file,
            filename="to_delete.txt"
        )
        doc_id = doc.id
        doc.delete()
        self.assertTrue(Document.all_objects.get(id=doc_id).is_deleted)
        self.assertFalse(Document.objects.filter(id=doc_id).exists())


class StorageAndServiceTests(TestCase):
    """Test suite verifying secure token signing and MediaService features."""

    def setUp(self):
        from apps.media.services import MediaService
        from apps.media.storage import (
            generate_secure_download_token,
            verify_secure_download_token,
        )
        self.org = Organization.objects.create(name="Service Org", slug="service-org")
        self.user = User.objects.create_user(username="serviceuser", password="password123")
        self.file_content = b"Binary stream content for testing MediaService."
        self.test_file = SimpleUploadedFile(
            name="stream_test.txt",
            content=self.file_content,
            content_type="text/plain"
        )
        self.generate_token = generate_secure_download_token
        self.verify_token = verify_secure_download_token
        self.service = MediaService

    def test_signed_token_generation_and_verification(self):
        """Verify generating and verifying signed document download tokens."""
        doc_id = "doc-12345"
        user_id = "user-67890"

        token = self.generate_token(doc_id, user_id)
        self.assertIsNotNone(token)
        self.assertIn(":", token)

        res = self.verify_token(token, max_age=60)
        self.assertIsNotNone(res)
        self.assertEqual(res, (doc_id, user_id))

    def test_verify_invalid_or_tampered_token(self):
        """Verify tampered or invalid token returns None."""
        invalid_res = self.verify_token("tampered_token_string")
        self.assertIsNone(invalid_res)

    def test_media_service_create_document(self):
        """Verify MediaService.create_document persists file with checksum."""
        doc = self.service.create_document(
            file_obj=self.test_file,
            organization=self.org,
            uploaded_by=self.user,
            filename="service_report.txt",
            is_public=True
        )
        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.filename, "service_report.txt")
        self.assertTrue(doc.is_public)
        self.assertEqual(len(doc.checksum_sha256), 64)


class DocumentAdminTests(TestCase):
    """Test suite verifying DocumentAdmin custom formatters and inlines."""

    def setUp(self):
        from apps.media.admin import DocumentAdmin
        self.admin = DocumentAdmin(Document, None)
        self.org = Organization.objects.create(name="Admin Org", slug="admin-org")
        self.test_file = SimpleUploadedFile("admin.txt", b"Admin content", content_type="text/plain")
        self.doc = Document.objects.create(
            organization=self.org,
            file=self.test_file,
            filename="admin.txt"
        )

    def test_admin_checksum_badge(self):
        """Verify checksum_badge produces monospaced HTML representation."""
        badge = self.admin.checksum_badge(self.doc)
        self.assertIn("<code", badge)
        self.assertIn(self.doc.checksum_sha256[:8], badge)

    def test_admin_file_size_display(self):
        """Verify file_size_display produces formatted string."""
        size_str = self.admin.file_size_display(self.doc)
        self.assertIn("B", size_str)


class DocumentAPITests(TestCase):
    """Test suite verifying REST API endpoints for upload, document listing, and downloading."""

    def setUp(self):
        from rest_framework.test import APIClient
        from apps.tenants.models import OrganizationMembership
        self.client = APIClient()
        self.org = Organization.objects.create(name="Doc API Org", slug="doc-api-org")
        self.user = User.objects.create_user(username="docuser", password="password123")
        OrganizationMembership.objects.create(user=self.user, organization=self.org, role=OrganizationMembership.ROLE_ADMIN)

        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_WORKSPACE_SLUG="doc-api-org")

        self.test_content = b"Binary API test file payload"
        self.upload_file = SimpleUploadedFile("api_upload.pdf", self.test_content, content_type="application/pdf")

    def test_upload_file_api(self):
        """Verify POST /api/v1/media/documents/upload/ handles multipart file upload."""
        res = self.client.post("/api/v1/media/documents/upload/", {
            "file": self.upload_file,
            "filename": "custom_api_upload.pdf",
            "is_public": False
        }, format="multipart")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["filename"], "custom_api_upload.pdf")
        self.assertEqual(len(res.data["checksum_sha256"]), 64)
        self.assertIn("download_url", res.data)

        # Check DB record
        doc = Document.objects.filter(id=res.data["id"]).first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.uploaded_by, self.user)
        self.assertEqual(doc.organization, self.org)

    def test_document_list_api(self):
        """Verify GET /api/v1/media/documents/ lists workspace documents."""
        doc = Document.objects.create(
            organization=self.org,
            file=self.upload_file,
            filename="list_doc.pdf",
            uploaded_by=self.user
        )
        res = self.client.get("/api/v1/media/documents/")
        self.assertEqual(res.status_code, 200)
        results = res.data.get("results") if isinstance(res.data, dict) else res.data
        self.assertGreaterEqual(len(results), 1)
        filenames = [d["filename"] for d in results]
        self.assertIn("list_doc.pdf", filenames)

    def test_document_download_api(self):
        """Verify GET /api/v1/media/documents/<id>/download/ streams file content."""
        doc = Document.objects.create(
            organization=self.org,
            file=self.upload_file,
            filename="download_me.txt",
            uploaded_by=self.user
        )
        res = self.client.get(f"/api/v1/media/documents/{doc.id}/download/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], doc.mime_type)
        self.assertIn("attachment", res["Content-Disposition"])




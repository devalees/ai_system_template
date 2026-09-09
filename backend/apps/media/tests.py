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

"""
Data models for Universal Document & Media Management.

Provides:
- Document: Multi-tenant, soft-deletable document model with SHA-256 checksums,
  MIME auto-detection, and GenericForeignKey model attachments.
"""

import hashlib
import mimetypes
import os
from typing import Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteModel
from apps.tenants.base_models import TenantAwareModel


def document_upload_to_path(instance, filename: str) -> str:
    """
    Partitioned upload path: documents/<org_slug>/<sha256[:2]>/<sha256>_<filename>
    """
    org_slug = instance.organization.slug if instance.organization else "global"
    checksum = instance.checksum_sha256 or "temp"
    prefix = checksum[:2] if len(checksum) >= 2 else "00"
    base_filename = os.path.basename(filename)
    return f"documents/{org_slug}/{prefix}/{checksum}_{base_filename}"


def calculate_sha256(file_obj) -> str:
    """Calculate SHA-256 hex digest for a file-like object."""
    hasher = hashlib.sha256()
    pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    for chunk in file_obj.chunks() if hasattr(file_obj, "chunks") else iter(lambda: file_obj.read(4096), b""):
        hasher.update(chunk)

    if hasattr(file_obj, "seek"):
        file_obj.seek(pos)
    return hasher.hexdigest()


def format_human_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class Document(TenantAwareModel, SoftDeleteModel):
    """
    Multi-tenant document and media record supporting SHA-256 integrity,
    deduplication hashes, and GenericForeignKey entity attachments.
    """
    file = models.FileField(
        upload_to=document_upload_to_path,
        max_length=512,
        verbose_name=_("File"),
        help_text=_("Binary file uploaded to media storage.")
    )
    filename = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Filename"),
        help_text=_("Original display filename of the document.")
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name=_("File Size (Bytes)"),
        help_text=_("Exact size of the binary file in bytes.")
    )
    mime_type = models.CharField(
        max_length=128,
        default="application/octet-stream",
        db_index=True,
        verbose_name=_("MIME Type"),
        help_text=_("Detected Content-Type / MIME string.")
    )
    checksum_sha256 = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default="",
        verbose_name=_("SHA-256 Checksum"),
        help_text=_("64-character hexadecimal SHA-256 digest for deduplication and integrity.")
    )
    is_public = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Public"),
        help_text=_("Indicates if document can be accessed publicly without token authentication.")
    )

    # Generic Foreign Key linkage to any model (AgentTask, User, Organization, etc.)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Content Type"),
        help_text=_("Model type of attached target entity.")
    )
    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Object ID"),
        help_text=_("Primary key of attached target entity.")
    )
    content_object = GenericForeignKey("content_type", "object_id")

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
        verbose_name=_("Uploaded By"),
        help_text=_("User or bot service account that uploaded this document.")
    )
    extra_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Extra Metadata"),
        help_text=_("Arbitrary key-value metadata (e.g. dimensions, page count, tags).")
    )

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "checksum_sha256"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["organization", "uploaded_by", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.filename} ({self.file_size_human}) [{self.checksum_sha256[:8]}]"

    @property
    def file_size_human(self) -> str:
        """Return formatted human-readable size string."""
        return format_human_size(self.file_size)

    def save(self, *args, **kwargs):
        """
        Auto-calculate filename, SHA-256 checksum, size, and MIME type before saving.
        """
        if self.file:
            if not self.filename:
                self.filename = os.path.basename(self.file.name)

            if hasattr(self.file, "size") and self.file.size:
                self.file_size = self.file.size

            if not self.checksum_sha256:
                try:
                    self.checksum_sha256 = calculate_sha256(self.file)
                except Exception:
                    pass

            if self.mime_type == "application/octet-stream" and self.filename:
                guessed_type, _ = mimetypes.guess_type(self.filename)
                if guessed_type:
                    self.mime_type = guessed_type

        super().save(*args, **kwargs)

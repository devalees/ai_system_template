"""
Django Admin interface for Universal Document & Media Management.
"""

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.media.models import Document


class GenericDocumentInline(GenericTabularInline):
    """
    Generic inline attachment component that can be added to any Django Admin model
    (e.g. AgentTask, User, Organization) to allow uploading and viewing attachments.
    """
    model = Document
    ct_field = "content_type"
    ct_fk_field = "object_id"
    extra = 1
    fields = ["file", "filename", "file_size_human", "mime_type", "is_public", "uploaded_by"]
    readonly_fields = ["file_size_human"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for inspecting system documents, SHA-256 checksums, and tenant scoping.
    """
    list_display = [
        "filename",
        "file_size_display",
        "mime_type",
        "checksum_badge",
        "is_public",
        "organization",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["is_public", "mime_type", "organization", "created_at"]
    search_fields = ["filename", "checksum_sha256", "uploaded_by__username"]
    readonly_fields = ["id", "file_size", "checksum_sha256", "created_at", "updated_at"]

    def file_size_display(self, obj: Document) -> str:
        """Display human-readable file size."""
        return obj.file_size_human

    file_size_display.short_description = _("Size")

    def checksum_badge(self, obj: Document) -> str:
        """Render monospaced SHA-256 checksum badge."""
        if not obj.checksum_sha256:
            return "-"
        truncated = f"{obj.checksum_sha256[:8]}...{obj.checksum_sha256[-8:]}"
        return format_html(
            '<code style="background: #eef2f6; color: #334155; padding: 2px 6px; border-radius: 4px; font-family: monospace;" title="{}">{}</code>',
            obj.checksum_sha256,
            truncated,
        )

    checksum_badge.short_description = _("SHA-256 Hash")

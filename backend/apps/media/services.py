"""
Document management services and binary file stream responses.
"""

import logging
import os
from typing import Any, Dict, Optional

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.utils.translation import gettext_lazy as _

from apps.media.models import Document, calculate_sha256

logger = logging.getLogger(__name__)


class MediaService:
    """Service layer managing Document ingestion and secure streaming downloads."""

    @classmethod
    def create_document(
        cls,
        file_obj,
        organization=None,
        uploaded_by=None,
        content_object=None,
        filename: Optional[str] = None,
        is_public: bool = False,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Create and persist a Document record from an uploaded file object.
        Automatically calculates SHA-256 checksum and extracts file metadata.
        """
        display_name = filename or getattr(file_obj, "name", "document")
        display_name = os.path.basename(display_name)

        checksum = calculate_sha256(file_obj)

        doc = Document(
            organization=organization,
            file=file_obj,
            filename=display_name,
            checksum_sha256=checksum,
            is_public=is_public,
            uploaded_by=uploaded_by,
            extra_metadata=extra_metadata or {},
        )

        if content_object:
            doc.content_object = content_object

        doc.save()
        return doc

    @classmethod
    def get_document_response(cls, document: Document, request, as_attachment: bool = True) -> FileResponse:
        """
        Construct permission-checked FileResponse binary stream for downloading or viewing a document.
        Enforces tenant workspace isolation unless document is_public.
        """
        user = getattr(request, "user", None)

        # Security permission validation
        if not document.is_public:
            if not user or not user.is_authenticated:
                raise PermissionDenied(_("Authentication required to access private documents."))

            # Workspace tenant scoping validation
            org = getattr(request, "tenant", None)
            if org and document.organization and document.organization != org:
                # Superusers or staff bypass tenant filter
                if not user.is_staff and not user.is_superuser:
                    raise PermissionDenied(_("You do not have access to documents in this workspace."))

        if not document.file or not os.path.exists(document.file.path):
            raise Http404(_("Document binary file not found on storage."))

        response = FileResponse(
            open(document.file.path, "rb"),
            content_type=document.mime_type or "application/octet-stream",
            as_attachment=as_attachment,
            filename=document.filename,
        )
        response["Content-Length"] = document.file_size
        return response

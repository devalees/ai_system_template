"""
DRF ViewSets and REST API Endpoints for Document upload and download streams.
"""

import logging
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.media.models import Document
from apps.media.serializers import DocumentSerializer, FileUploadSerializer
from apps.media.services import MediaService

logger = logging.getLogger(__name__)


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for uploading, managing, listing, and downloading system Documents.
    Operations are automatically scoped to the active workspace tenant.
    """
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Filter documents by active workspace tenant."""
        qs = Document.objects.all()

        org = getattr(self.request, "tenant", None)
        if org:
            qs = qs.filter(organization=org)

        is_public_param = self.request.query_params.get("is_public")
        if is_public_param is not None:
            if is_public_param.lower() in ("true", "1"):
                qs = qs.filter(is_public=True)
            elif is_public_param.lower() in ("false", "0"):
                qs = qs.filter(is_public=False)

        mime_param = self.request.query_params.get("mime_type")
        if mime_param:
            qs = qs.filter(mime_type__icontains=mime_param)

        return qs.order_by("-created_at")

    @action(detail=False, methods=["post"], url_path="upload")
    def upload_file(self, request):
        """
        Upload binary document file via multipart payload.
        Auto-calculates SHA-256 checksum, file size, and binds active tenant.
        """
        upload_serializer = FileUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        validated_data = upload_serializer.validated_data

        file_obj = validated_data["file"]
        is_public = validated_data.get("is_public", False)
        custom_filename = validated_data.get("filename")
        object_id = validated_data.get("object_id")
        content_type = validated_data.get("target_content_type")

        org = getattr(request, "tenant", None)

        doc = MediaService.create_document(
            file_obj=file_obj,
            organization=org,
            uploaded_by=request.user,
            filename=custom_filename,
            is_public=is_public,
        )

        if content_type and object_id:
            doc.content_type = content_type
            doc.object_id = object_id
            doc.save(update_fields=["content_type", "object_id"])

        return Response(self.get_serializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """
        Stream binary document file with workspace security permission validation.
        """
        document = self.get_object()
        return MediaService.get_document_response(document, request, as_attachment=True)

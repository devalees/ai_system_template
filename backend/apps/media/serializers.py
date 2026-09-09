"""
DRF Serializers for Universal Document & Media Management.
"""

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.media.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document metadata, Generic FK details, and download URLs."""

    uploaded_by_username = serializers.ReadOnlyField(source="uploaded_by.username", default=None)
    download_url = serializers.SerializerMethodField()
    file_size_human = serializers.ReadOnlyField()

    class Meta:
        model = Document
        fields = [
            "id",
            "organization",
            "filename",
            "file",
            "file_size",
            "file_size_human",
            "mime_type",
            "checksum_sha256",
            "is_public",
            "content_type",
            "object_id",
            "uploaded_by",
            "uploaded_by_username",
            "extra_metadata",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "file_size",
            "checksum_sha256",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]

    def get_download_url(self, obj: Document) -> str:
        """Construct relative URL endpoint for downloading binary file stream."""
        return f"/api/v1/media/documents/{obj.id}/download/"


class FileUploadSerializer(serializers.Serializer):
    """Serializer for multipart file upload payload validation."""

    file = serializers.FileField(help_text="Binary document or media file.")
    is_public = serializers.BooleanField(default=False, required=False)
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True)
    model_app_label = serializers.CharField(max_length=64, required=False, allow_blank=True)
    model_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    object_id = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate model_app_label and model_name resolution if provided."""
        app_label = attrs.get("model_app_label")
        model_name = attrs.get("model_name")
        if app_label and model_name:
            try:
                attrs["target_content_type"] = ContentType.objects.get(app_label=app_label, model=model_name.lower())
            except ContentType.DoesNotExist:
                raise serializers.ValidationError(
                    f"Target model '{app_label}.{model_name}' does not exist in ContentType catalog."
                )
        return attrs

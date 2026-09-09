"""
Serializers for Developer API Gateway endpoints.
"""

from rest_framework import serializers
from apps.api_gateway.models import APIKey, InboundWebhook, WebhookEvent


class APIKeyListSerializer(serializers.ModelSerializer):
    """Serializer for displaying stored API key details (secret key hidden)."""
    user_email = serializers.EmailField(source="user.email", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "prefix",
            "user",
            "user_email",
            "organization",
            "scopes",
            "allowed_ips",
            "expires_at",
            "is_active",
            "is_expired",
            "last_used_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "prefix", "user", "organization", "last_used_at", "created_at", "updated_at"]


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new API key.
    Returns the unhashed raw secret key ONCE upon creation response.
    """
    raw_key = serializers.CharField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "scopes",
            "allowed_ips",
            "expires_at",
            "raw_key",
            "created_at",
        ]
        read_only_fields = ["id", "raw_key", "created_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        tenant = getattr(self.context["request"], "tenant", None)
        
        name = validated_data.get("name")
        scopes = validated_data.get("scopes", ["read", "write"])
        allowed_ips = validated_data.get("allowed_ips", [])
        expires_at = validated_data.get("expires_at", None)

        key_instance, raw_secret_key = APIKey.generate_key(
            name=name,
            user=user,
            organization=tenant,
            scopes=scopes,
            expires_at=expires_at,
            allowed_ips=allowed_ips,
        )
        key_instance.raw_key = raw_secret_key
        return key_instance


class InboundWebhookSerializer(serializers.ModelSerializer):
    """Serializer for managing inbound webhook endpoint configurations."""

    class Meta:
        model = InboundWebhook
        fields = [
            "id",
            "name",
            "endpoint_slug",
            "secret_token",
            "provider",
            "is_active",
            "organization",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]


class WebhookEventSerializer(serializers.ModelSerializer):
    """Read-only serializer for auditing received webhook events."""

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "webhook",
            "event_type",
            "payload",
            "headers",
            "status",
            "error_message",
            "organization",
            "created_at",
        ]
        read_only_fields = fields

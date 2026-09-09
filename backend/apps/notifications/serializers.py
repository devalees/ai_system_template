"""
DRF Serializers for Universal Notifications Engine.
"""

from rest_framework import serializers

from apps.notifications.models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification inbox records."""

    recipient_username = serializers.ReadOnlyField(source="recipient.username")
    actor_username = serializers.ReadOnlyField(source="actor.username", default=None)

    class Meta:
        model = Notification
        fields = [
            "id",
            "organization",
            "recipient",
            "recipient_username",
            "actor",
            "actor_username",
            "level",
            "title",
            "message",
            "action_url",
            "read_at",
            "is_read",
            "channel",
            "extra_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "recipient",
            "actor",
            "read_at",
            "created_at",
            "updated_at",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user notification delivery preferences."""

    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "user",
            "user_username",
            "in_app_enabled",
            "email_enabled",
            "webhook_enabled",
            "slack_enabled",
            "webhook_url",
            "slack_webhook_url",
            "channel_config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

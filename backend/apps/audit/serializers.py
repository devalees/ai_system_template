"""
Serializers for Comprehensive Activity Audit Trail REST API.
"""

from rest_framework import serializers

from apps.audit.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for ActivityLog entries.
    """
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True, default=None)
    content_type_model = serializers.CharField(source="content_type.model", read_only=True, default=None)
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    actor_type_display = serializers.CharField(source="get_actor_type_display", read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "timestamp",
            "actor",
            "actor_username",
            "actor_type",
            "actor_type_display",
            "action",
            "action_display",
            "status",
            "status_display",
            "organization",
            "organization_slug",
            "content_type",
            "content_type_model",
            "object_id",
            "object_repr",
            "changes",
            "ip_address",
            "user_agent",
            "request_id",
            "metadata",
        ]
        read_only_fields = fields

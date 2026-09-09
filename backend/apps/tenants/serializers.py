"""
REST API Serializers for Multi-Tenancy, Organizations, Members, and Invitations.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.tenants.models import Organization, OrganizationMembership, OrganizationInvitation

User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    """Minimal representation of a User for membership lists."""
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    """Serializer for organization memberships."""
    user = UserBriefSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user",
        write_only=True,
        required=False
    )

    class Meta:
        model = OrganizationMembership
        fields = (
            "id",
            "organization",
            "user",
            "user_id",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organizations / Workspaces."""
    active_members_count = serializers.IntegerField(read_only=True)
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "tier",
            "max_users",
            "active_members_count",
            "current_user_role",
            "domain",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_current_user_role(self, obj) -> str:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user, is_active=True).first()
            return membership.role if membership else "none"
        return "none"


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    """Serializer for sending and viewing organization invitations."""
    invited_by = UserBriefSerializer(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = (
            "id",
            "organization",
            "email",
            "role",
            "token",
            "invited_by",
            "expires_at",
            "status",
            "is_valid",
            "created_at",
        )
        read_only_fields = ("id", "organization", "token", "invited_by", "expires_at", "status", "created_at")

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["invited_by"] = request.user
        return super().create(validated_data)


class AcceptInvitationSerializer(serializers.Serializer):
    """Serializer for validating an invitation acceptance request."""
    token = serializers.CharField(required=True, max_length=64)

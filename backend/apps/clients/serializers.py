"""
Serializers for Client Management REST API.
"""

from rest_framework import serializers
from apps.clients.models import Client


class ClientSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Client entities including live budget calculations.
    """
    ai_budget_percentage = serializers.ReadOnlyField()
    ai_budget_status = serializers.ReadOnlyField()
    can_use_ai = serializers.SerializerMethodField()
    linked_users_count = serializers.ReadOnlyField()
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = Client
        fields = [
            'id',
            'organization',
            'organization_name',
            'name',
            'slug',
            'primary_contact_name',
            'primary_contact_email',
            'primary_contact_phone',
            'status',
            'notes',
            'is_ai_enabled',
            'ai_budget_usd',
            'ai_spend_usd',
            'ai_budget_percentage',
            'ai_budget_status',
            'can_use_ai',
            'linked_users_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'ai_budget_percentage',
            'ai_budget_status',
            'can_use_ai',
            'linked_users_count',
            'created_at',
            'updated_at',
        ]

    def get_can_use_ai(self, obj: Client) -> bool:
        return obj.can_use_ai()

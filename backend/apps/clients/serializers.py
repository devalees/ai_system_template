"""
Serializers for Client Management REST API.
"""

from rest_framework import serializers
from apps.clients.models import Client
from apps.tenants.models import Organization


class ClientSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Client entities including live budget calculations.
    """
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        required=False,
        allow_null=True
    )
    slug = serializers.SlugField(required=False, allow_blank=True)
    ai_budget_percentage = serializers.ReadOnlyField()
    ai_budget_status = serializers.ReadOnlyField()
    can_use_ai = serializers.SerializerMethodField()
    linked_users_count = serializers.ReadOnlyField()
    documents_count = serializers.SerializerMethodField()
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
            'documents_count',
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

    def to_internal_value(self, data):
        from django.utils.text import slugify
        from apps.tenants.models import Organization, OrganizationMembership
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)
        
        if not mutable.get('organization'):
            request = self.context.get('request')
            user = request.user if request else None
            mem = OrganizationMembership.objects.filter(user=user, is_active=True).first() if user and user.is_authenticated else None
            org = mem.organization if mem else Organization.objects.first()
            if org:
                mutable['organization'] = str(org.id)

        if not mutable.get('slug') and mutable.get('name'):
            base_slug = slugify(mutable['name']) or 'client'
            unique_slug = base_slug
            idx = 1
            org_id = mutable.get('organization')
            while Client.objects.filter(organization_id=org_id, slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{idx}"
                idx += 1
            mutable['slug'] = unique_slug

        return super().to_internal_value(mutable)

    def get_can_use_ai(self, obj: Client) -> bool:
        return obj.can_use_ai()

    def get_documents_count(self, obj: Client) -> int:
        return getattr(obj, 'documents', None).count() if hasattr(obj, 'documents') else 0

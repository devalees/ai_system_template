from rest_framework import serializers
from .models import HandshakeLog, Profile, SpendReport, AgentTask, ModelBenchmark, ProviderCredential, AgentProfile


class HandshakeRequestSerializer(serializers.Serializer):
    agent_id = serializers.CharField(max_length=120, default='hermes-agent')
    version = serializers.CharField(max_length=60, required=False, default='1.0.0')
    timestamp = serializers.CharField(max_length=100, required=False)
    message = serializers.CharField(max_length=500, required=False, default='Ping from Hermes Agent')
    metadata = serializers.DictField(required=False, default=dict)


class HandshakeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandshakeLog
        fields = '__all__'


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)
    ai_budget_percentage = serializers.FloatField(read_only=True)
    ai_budget_status = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'



# Backward compatibility alias
AgentProfileSerializer = ProfileSerializer


class SpendReportSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = SpendReport
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'created_by')


class AgentTaskSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source='assigned_profile.name', read_only=True)
    profile_display_name = serializers.CharField(source='assigned_profile.display_name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = AgentTask
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'created_by')

    def to_internal_value(self, data):
        # Support aliases from frontend: 'name' -> 'task_name', 'profile_name' -> 'assigned_profile'
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'name' in mutable_data and 'task_name' not in mutable_data:
            mutable_data['task_name'] = mutable_data['name']
        
        if mutable_data.get('status') == 'in_progress':
            mutable_data['status'] = 'running'

        prof_input = mutable_data.get('profile_name') or mutable_data.get('assigned_profile')
        if prof_input and isinstance(prof_input, str):
            prof = AgentProfile.objects.filter(name=prof_input).first()
            if prof:
                mutable_data['assigned_profile'] = str(prof.id)

        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Normalize 'running' to 'in_progress' for frontend Kanban alignment
        if data.get('status') == 'running':
            data['status'] = 'in_progress'
        data['name'] = instance.task_name
        return data


class ProviderCredentialSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    masked_key = serializers.CharField(read_only=True)
    provider_display = serializers.CharField(source='get_provider_type_display', read_only=True)

    class Meta:
        model = ProviderCredential
        fields = [
            'id', 'name', 'provider_type', 'provider_display', 'base_url',
            'is_active', 'is_default', 'organization', 'metadata', 'masked_key', 'api_key'
        ]
        read_only_fields = ['id', 'masked_key', 'provider_display']

    def create(self, validated_data):
        raw_key = validated_data.pop('api_key', '')
        cred = ProviderCredential(**validated_data)
        if raw_key:
            cred.api_key = raw_key
        cred.save()
        return cred

    def update(self, instance, validated_data):
        raw_key = validated_data.pop('api_key', None)
        if raw_key is not None:
            instance.api_key = raw_key
        return super().update(instance, validated_data)


class TaskVerdictSerializer(serializers.Serializer):
    verdict = serializers.ChoiceField(choices=['approved', 'changes_requested'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    reviewer_profile = serializers.CharField(required=False, default='qa_auditor')


class ModelBenchmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelBenchmark
        fields = '__all__'


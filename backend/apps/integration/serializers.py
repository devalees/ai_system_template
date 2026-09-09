from rest_framework import serializers
from .models import HandshakeLog, Profile, SpendReport, AgentTask

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


class TaskVerdictSerializer(serializers.Serializer):
    verdict = serializers.ChoiceField(choices=['approved', 'changes_requested'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    reviewer_profile = serializers.CharField(required=False, default='qa_auditor')

from rest_framework import serializers
from .models import HandshakeLog, AgentProfile, SpendReport, AgentTask

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


class AgentProfileSerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = AgentProfile
        fields = '__all__'


class SpendReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpendReport
        fields = '__all__'


class AgentTaskSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source='assigned_profile.name', read_only=True)
    profile_display_name = serializers.CharField(source='assigned_profile.display_name', read_only=True)

    class Meta:
        model = AgentTask
        fields = '__all__'


class TaskVerdictSerializer(serializers.Serializer):
    verdict = serializers.ChoiceField(choices=['approved', 'changes_requested'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    reviewer_profile = serializers.CharField(required=False, default='qa_auditor')

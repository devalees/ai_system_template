from rest_framework import serializers
from .models import HandshakeLog, AgentTask

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


class AgentTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTask
        fields = '__all__'

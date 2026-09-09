"""
DRF Serializers for Centralized Automation Engine.
"""

from rest_framework import serializers
from .models import AutomationRule, AutomationLog


class AutomationRuleSerializer(serializers.ModelSerializer):
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    execution_mode_display = serializers.CharField(source='get_execution_mode_display', read_only=True)

    class Meta:
        model = AutomationRule
        fields = '__all__'


class AutomationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)

    class Meta:
        model = AutomationLog
        fields = '__all__'

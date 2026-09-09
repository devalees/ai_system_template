"""
DRF Serializers for Centralized Automation Engine.
"""

from rest_framework import serializers
from .models import AutomationTrigger, AutomationAction, AutomationLog, AutomationRule


class AutomationActionSerializer(serializers.ModelSerializer):
    action_category_display = serializers.CharField(source='get_action_category_display', read_only=True)

    class Meta:
        model = AutomationAction
        fields = '__all__'


class AutomationTriggerSerializer(serializers.ModelSerializer):
    trigger_type_display = serializers.CharField(source='get_trigger_type_display', read_only=True)
    execution_mode_display = serializers.CharField(source='get_execution_mode_display', read_only=True)
    actions = AutomationActionSerializer(many=True, read_only=True)

    class Meta:
        model = AutomationTrigger
        fields = '__all__'


# Backward-compatibility alias
AutomationRuleSerializer = AutomationTriggerSerializer


class AutomationLogSerializer(serializers.ModelSerializer):
    trigger_name = serializers.CharField(source='trigger.name', read_only=True)
    action_name = serializers.CharField(source='action.name', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True)

    class Meta:
        model = AutomationLog
        fields = '__all__'

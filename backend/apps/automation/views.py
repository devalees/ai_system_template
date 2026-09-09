"""
REST API Endpoints for Centralized Automation Engine.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.integration.views import StrictDjangoModelPermissions
from .models import AutomationRule, AutomationLog
from .serializers import AutomationRuleSerializer, AutomationLogSerializer
from .registry import ServiceRegistry
from .tasks import execute_automation_rule_task


class AutomationRuleViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for managing Automation Rules.
    """
    queryset = AutomationRule.objects.all()
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    @action(detail=True, methods=['post'], url_path='trigger')
    def trigger_rule(self, request, pk=None):
        """
        On-demand trigger endpoint: immediately queues this rule to Celery.
        """
        rule = self.get_object()
        trigger_context = request.data if isinstance(request.data, dict) else {}
        async_res = execute_automation_rule_task.delay(
            rule.id,
            trigger_context,
            f"api_trigger:{request.user.username}"
        )
        return Response({
            "status": "queued",
            "rule_id": rule.id,
            "rule_name": rule.name,
            "task_id": async_res.id,
            "message": f"Rule '{rule.name}' queued to Celery worker."
        }, status=status.HTTP_202_ACCEPTED)


class AutomationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for reviewing automation execution logs.
    """
    queryset = AutomationLog.objects.all()
    serializer_class = AutomationLogSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]
    filterset_fields = ['status', 'rule']


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_registered_services(request):
    """
    Returns directory of registered services, actions, and Hermes agent profiles.
    """
    actions = ServiceRegistry.list_actions()
    data = [a.to_dict() for a in actions]
    return Response({
        "count": len(data),
        "services": data,
        "available_models": ServiceRegistry.get_registered_model_choices(),
    })

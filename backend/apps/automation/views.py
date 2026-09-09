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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def model_introspection(request):
    """
    Dynamic Model & Field Introspection API for Automation Actions.
    Provides schema, field types, requirement constraints, and choices for a requested model,
    or lists all discoverable system models.
    """
    from django.apps import apps
    model_param = request.query_params.get('model', '').strip()

    if not model_param:
        choices = ServiceRegistry.get_registered_model_choices()
        return Response({
            "available_models": choices,
            "count": sum(len(models) for _, models in choices),
        })

    if '.' not in model_param:
        return Response(
            {"error": f"Invalid model identifier '{model_param}'. Expected format: 'app_label.ModelName'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        model_cls = apps.get_model(model_param)
        if not model_cls:
            raise LookupError()
    except (LookupError, ValueError):
        return Response(
            {"error": f"Model '{model_param}' not found in installed Django apps."},
            status=status.HTTP_400_BAD_REQUEST
        )

    fields_data = []
    required_fields = []
    for field in model_cls._meta.fields:
        is_pk = field.primary_key
        is_editable = field.editable
        has_default = field.has_default()
        is_required = not field.blank and not field.null and not has_default and not is_pk

        if is_required:
            required_fields.append(field.name)

        choices = []
        if field.choices:
            for val, label in field.choices:
                choices.append({"value": str(val), "label": str(label)})

        field_info = {
            "name": field.name,
            "verbose_name": str(field.verbose_name).title(),
            "type": field.get_internal_type(),
            "required": is_required,
            "editable": is_editable,
            "primary_key": is_pk,
            "help_text": str(field.help_text) if field.help_text else "",
            "choices": choices,
        }
        if field.is_relation and field.related_model:
            field_info["related_model"] = f"{field.related_model._meta.app_label}.{field.related_model.__name__}"

        fields_data.append(field_info)

    return Response({
        "model": model_param,
        "app_label": model_cls._meta.app_label,
        "model_name": model_cls._meta.model_name,
        "verbose_name": str(model_cls._meta.verbose_name).title(),
        "verbose_name_plural": str(model_cls._meta.verbose_name_plural).title(),
        "required_fields": required_fields,
        "fields": fields_data,
    })

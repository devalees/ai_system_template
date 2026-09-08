import datetime
import requests
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import HandshakeLog, AgentProfile, SpendReport, AgentTask
from .serializers import (
    HandshakeRequestSerializer,
    HandshakeLogSerializer,
    AgentProfileSerializer,
    SpendReportSerializer,
    AgentTaskSerializer,
    TaskVerdictSerializer,
)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Returns operational health of Django backend, PostgreSQL database, and Redis cache.
    """
    db_status = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    redis_status = "unconfigured"
    redis_url = getattr(settings, 'REDIS_URL', None)
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url, socket_timeout=2)
            if r.ping():
                redis_status = "ok"
        except Exception as exc:
            redis_status = f"error: {str(exc)}"

    return Response({
        "status": "healthy" if db_status == "ok" else "degraded",
        "service": "django-backend",
        "database": db_status,
        "redis": redis_status,
        "server_time": timezone.now().isoformat(),
        "hermes_gateway_target": settings.HERMES_GATEWAY_URL,
        "active_profiles_count": AgentProfile.objects.filter(is_active=True).count(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def agent_handshake(request):
    """
    Receives a handshake ping from an autonomous agent (Hermes),
    persists the handshake payload to the database, and returns acknowledgment.
    """
    serializer = HandshakeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))

    ack_payload = {
        "status": "acknowledged",
        "message": "Handshake accepted by Django backend",
        "received_agent_id": data.get('agent_id'),
        "server_time": timezone.now().isoformat(),
    }

    log_entry = HandshakeLog.objects.create(
        agent_id=data.get('agent_id', 'hermes-agent'),
        version=data.get('version', '1.0.0'),
        client_ip=client_ip,
        payload=request.data,
        server_response=ack_payload,
        status='success'
    )

    ack_payload["log_id"] = str(log_entry.id)
    return Response(ack_payload, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_handshake_logs(request):
    """
    Returns recent handshake logs.
    """
    logs = HandshakeLog.objects.all()[:50]
    serializer = HandshakeLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def ping_hermes_gateway(request):
    """
    Reverse connectivity test: Django initiates HTTP request to Hermes Gateway.
    """
    target_url = settings.HERMES_GATEWAY_URL.rstrip('/')
    headers = {}
    if settings.HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {settings.HERMES_API_KEY}"

    try:
        resp = requests.get(f"{target_url}/", headers=headers, timeout=5)
        return Response({
            "status": "connected",
            "gateway_url": target_url,
            "hermes_http_status": resp.status_code,
            "response_preview": resp.text[:300],
        })
    except Exception as exc:
        return Response({
            "status": "unreachable",
            "gateway_url": target_url,
            "error": str(exc)
        }, status=status.HTTP_502_BAD_GATEWAY)


class AgentProfileViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Hermes Agent Profiles (digital employees).
    """
    queryset = AgentProfile.objects.all()
    serializer_class = AgentProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = 'name'


class SpendReportViewSet(viewsets.ModelViewSet):
    """
    Ingestion and query API for LLM spend reports from cost_controller.
    """
    queryset = SpendReport.objects.all()
    serializer_class = SpendReportSerializer
    permission_classes = [AllowAny]


class AgentTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Agent Tasks supporting the review pipeline.
    """
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'], url_path='submit-verdict')
    def submit_verdict(self, request, pk=None):
        """
        Review gate endpoint: allows qa_auditor to submit 'approved' or 'changes_requested'.
        """
        task = self.get_object()
        serializer = TaskVerdictSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        verdict = serializer.validated_data['verdict']
        notes = serializer.validated_data.get('notes', '')

        task.review_verdict = verdict
        task.reviewer_notes = notes

        if verdict == 'approved':
            task.status = 'completed'
            task.completed_at = timezone.now()
        else:
            task.status = 'pending'  # Returns to implementer for revisions

        task.save()
        return Response({
            "status": "verdict_recorded",
            "task_id": str(task.id),
            "new_task_status": task.status,
            "verdict": verdict,
            "notes": notes,
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def list_hermes_providers(request):
    """
    Returns list of canonical inference providers supported by Hermes Agent.
    """
    from .services import get_providers
    return Response(get_providers())


@api_view(['GET'])
@permission_classes([AllowAny])
def list_hermes_models(request):
    """
    Returns available models for a given provider with context length and pricing.
    """
    from .services import get_models_for_provider
    provider = request.query_params.get('provider', 'openrouter')
    models_data = get_models_for_provider(provider)
    return Response({
        "provider": provider,
        "count": len(models_data),
        "models": models_data,
    })


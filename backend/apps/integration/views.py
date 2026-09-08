import datetime
import requests
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import HandshakeLog, AgentTask
from .serializers import (
    HandshakeRequestSerializer,
    HandshakeLogSerializer,
    AgentTaskSerializer,
)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Returns the operational health of the Django backend,
    PostgreSQL database connection, and Redis cache.
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
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def agent_handshake(request):
    """
    Receives a handshake ping from an autonomous agent (Hermes),
    persists the handshake payload to the database, and returns
    an acknowledgment response.
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
    Reverse connectivity test: Django initiates an HTTP request
    to the Hermes Agent Gateway to verify bidirectional network path.
    """
    target_url = settings.HERMES_GATEWAY_URL.rstrip('/')
    headers = {}
    if settings.HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {settings.HERMES_API_KEY}"

    try:
        # Ping root or health endpoint of Hermes Gateway
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


class AgentTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Agent Tasks.
    """
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [AllowAny]

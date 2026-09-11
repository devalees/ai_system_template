import datetime
import requests
from django.conf import settings
from django.db import connection, models
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from .models import HandshakeLog, Profile, AgentProfile, SpendReport, AgentTask
from .serializers import (
    HandshakeRequestSerializer,
    HandshakeLogSerializer,
    ProfileSerializer,
    SpendReportSerializer,
    AgentTaskSerializer,
    TaskVerdictSerializer,
)

class StrictDjangoModelPermissions(DjangoModelPermissions):
    """
    Extends DjangoModelPermissions to enforce view_<model> on GET/HEAD/OPTIONS.
    Ensures complete RBAC coverage across all HTTP verbs.
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

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
        "active_profiles_count": Profile.objects.filter(is_active=True).count(),
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
@permission_classes([IsAuthenticated])
def list_handshake_logs(request):
    """
    Returns recent handshake logs.
    """
    logs = HandshakeLog.objects.all()[:50]
    serializer = HandshakeLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
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


class ProfileViewSet(viewsets.ModelViewSet):
    """
    CRUD API for User Profiles and AI Agent Service Accounts.
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]
    lookup_field = 'name'

    def get_object(self):
        """Allows lookup by name, hermes_profile_name, or user username."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        val = self.kwargs.get(lookup_url_kwarg)
        try:
            return self.get_queryset().get(
                models.Q(name=val) | models.Q(hermes_profile_name=val) | models.Q(user__username=val)
            )
        except Profile.DoesNotExist:
            return super().get_object()


# Backward compatibility alias
AgentProfileViewSet = ProfileViewSet


class SpendReportViewSet(viewsets.ModelViewSet):
    """
    Ingestion and query API for LLM spend reports from cost_controller.
    """
    queryset = SpendReport.objects.all()
    serializer_class = SpendReportSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)


class AgentTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Agent Tasks supporting the review pipeline.
    """
    queryset = AgentTask.objects.all()
    serializer_class = AgentTaskSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(
        detail=True,
        methods=['post'],
        url_path='submit-verdict',
        permission_classes=[IsAuthenticated]
    )
    def submit_verdict(self, request, pk=None):
        """
        Review gate endpoint: allows qa_auditor to submit 'approved' or 'changes_requested'.
        """
        # Strict RBAC gate: only QA Auditor service account with change_agenttask permission or superuser
        is_qa_auditor = (
            request.user.is_superuser or (
                request.user.has_perm('integration.change_agenttask') and
                request.user.groups.filter(name='Agent_QAAuditor').exists()
            )
        )
        if not is_qa_auditor:
            return Response(
                {"detail": "Only QA Auditor service account (Agent_QAAuditor) is authorized to submit review verdicts."},
                status=status.HTTP_403_FORBIDDEN
            )

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


@api_view(['GET'])
@permission_classes([AllowAny])
def list_hermes_profiles(request):
    """
    Returns available Hermes Agent profiles discovered live from runtime/declarative dirs.
    Used by Django Admin dropdown and dynamic profile selectors.
    """
    from .services.hermes_discovery import HermesDiscoveryService
    profiles = HermesDiscoveryService.list_available_profiles()
    return Response({
        "count": len(profiles),
        "profiles": profiles
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def list_model_benchmarks(request):
    """
    Returns frontier model benchmark scores (e.g. DeepSWE) with intelligence scores and costs.
    Accepts optional ?benchmark=DeepSWE or ?model=google/gemini-2.5-flash filters.
    """
    from .models import ModelBenchmark
    from .serializers import ModelBenchmarkSerializer
    from .services.benchmark_sync import sync_benchmarks

    # Auto-seed reference baseline if table is empty
    if not ModelBenchmark.objects.exists():
        sync_benchmarks()

    qs = ModelBenchmark.objects.all()
    benchmark_name = request.query_params.get('benchmark')
    if benchmark_name:
        qs = qs.filter(benchmark_name__iexact=benchmark_name)
    model_id = request.query_params.get('model')
    if model_id:
        qs = qs.filter(model_identifier__iexact=model_id)

    serializer = ModelBenchmarkSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "benchmarks": serializer.data,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_budget_status(request):
    """
    Client AI Budget & Spend Milestone Endpoint.
    GET /api/hermes/client-budget-status/?client_id=<UUID | username | name>
    POST /api/hermes/client-budget-status/ (Logs spend delta or updates allocation)
    """
    client_id = request.query_params.get('client_id') or request.data.get('client_id')
    client_profile = None
    client_obj = None

    if client_id:
        try:
            import uuid
            val_uuid = uuid.UUID(str(client_id))
            from apps.clients.models import Client
            client_obj = Client.objects.filter(id=val_uuid, is_deleted=False).first()
        except (ValueError, AttributeError):
            pass

        if not client_obj:
            from apps.clients.models import Client
            client_obj = Client.objects.filter(
                models.Q(slug=client_id) | models.Q(name=client_id),
                is_deleted=False
            ).first()

    elif request.user.is_authenticated:
        user_profile = getattr(request.user, 'profile', None)
        if user_profile and user_profile.client:
            client_obj = user_profile.client

    if client_obj:
        if request.method == 'POST':
            spend_delta = request.data.get('spend_delta_usd')
            budget_override = request.data.get('ai_budget_usd')

            if spend_delta is not None:
                try:
                    from decimal import Decimal
                    delta = Decimal(str(spend_delta))
                    client_obj.ai_spend_usd += delta
                except Exception as e:
                    return Response({"detail": f"Invalid spend_delta_usd value: {e}"}, status=status.HTTP_400_BAD_REQUEST)

            if budget_override is not None:
                try:
                    from decimal import Decimal
                    client_obj.ai_budget_usd = Decimal(str(budget_override))
                except Exception as e:
                    return Response({"detail": f"Invalid ai_budget_usd value: {e}"}, status=status.HTTP_400_BAD_REQUEST)

            client_obj.save(update_fields=['ai_spend_usd', 'ai_budget_usd'])

        pct = client_obj.ai_budget_percentage
        return Response({
            "client_id": str(client_obj.id),
            "slug": client_obj.slug,
            "name": client_obj.name,
            "organization_name": client_obj.organization.name if client_obj.organization else "",
            "is_ai_enabled": client_obj.is_ai_enabled,
            "can_use_ai": client_obj.can_use_ai(),
            "ai_budget_usd": str(client_obj.ai_budget_usd),
            "ai_spend_usd": str(client_obj.ai_spend_usd),
            "percentage_used": pct,
            "budget_status": client_obj.ai_budget_status,
            "milestones": {
                "silent_check_25_reached": pct >= 25.0,
                "velocity_check_50_reached": pct >= 50.0,
                "advisory_75_reached": pct >= 75.0,
                "exceeded_100_reached": pct >= 100.0,
            }
        })

    # Fallback to Profile model lookup for legacy compatibility
    if client_id:
        try:
            import uuid
            val_uuid = uuid.UUID(str(client_id))
            client_profile = Profile.objects.filter(id=val_uuid).first()
        except (ValueError, AttributeError):
            pass

        if not client_profile:
            client_profile = Profile.objects.filter(
                models.Q(user__username=client_id) | models.Q(name=client_id)
            ).first()
    elif request.user.is_authenticated:
        client_profile = getattr(request.user, 'profile', None)

    if not client_profile:
        return Response(
            {"detail": "Client entity or profile not found. Please provide a valid client_id parameter."},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'POST':
        spend_delta = request.data.get('spend_delta_usd')
        budget_override = request.data.get('ai_budget_usd')

        if spend_delta is not None:
            try:
                from decimal import Decimal
                delta = Decimal(str(spend_delta))
                client_profile.ai_spend_usd += delta
            except Exception as e:
                return Response({"detail": f"Invalid spend_delta_usd value: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        if budget_override is not None:
            try:
                from decimal import Decimal
                client_profile.ai_budget_usd = Decimal(str(budget_override))
            except Exception as e:
                return Response({"detail": f"Invalid ai_budget_usd value: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        client_profile.save(update_fields=['ai_spend_usd', 'ai_budget_usd'])

    pct = client_profile.ai_budget_percentage
    return Response({
        "client_id": str(client_profile.id),
        "username": client_profile.user.username if client_profile.user else "",
        "name": client_profile.name,
        "display_name": client_profile.display_name,
        "user_type": client_profile.user_type,
        "ai_budget_usd": str(client_profile.ai_budget_usd),
        "ai_spend_usd": str(client_profile.ai_spend_usd),
        "percentage_used": pct,
        "budget_status": client_profile.ai_budget_status,
        "milestones": {
            "silent_check_25_reached": pct >= 25.0,
            "velocity_check_50_reached": pct >= 50.0,
            "advisory_75_reached": pct >= 75.0,
            "exceeded_100_reached": pct >= 100.0,
        }
    })





"""
API views for Developer API Gateway, Key Management, and Inbound Webhook Ingestion.
"""

import json
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_gateway.models import APIKey, InboundWebhook, WebhookEvent
from apps.api_gateway.serializers import (
    APIKeyListSerializer,
    APIKeyCreateSerializer,
    InboundWebhookSerializer,
    WebhookEventSerializer,
)
from apps.api_gateway.signature import verify_hmac_signature


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing developer API keys.
    Allows listing existing keys, generating new raw secret keys, and revoking keys.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = APIKey.objects.filter(is_deleted=False)
        if tenant:
            qs = qs.filter(organization=tenant)
        else:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeyListSerializer

    def perform_destroy(self, instance):
        instance.delete()


class InboundWebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for configuring inbound webhook endpoints."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InboundWebhookSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = InboundWebhook.objects.filter(is_deleted=False)
        if tenant:
            qs = qs.filter(organization=tenant)
        return qs

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        serializer.save(organization=tenant)

    def perform_destroy(self, instance):
        instance.delete()


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for inspecting received webhook event logs."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WebhookEventSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = WebhookEvent.objects.filter(is_deleted=False)
        if tenant:
            qs = qs.filter(organization=tenant)
        return qs


class InboundWebhookIngestView(APIView):
    """
    Public Endpoint for receiving inbound HTTP webhooks from external SaaS services.
    Validates provider HMAC signatures and logs events.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, slug: str):
        try:
            webhook = InboundWebhook.all_objects.get(
                endpoint_slug=slug,
                is_active=True,
                is_deleted=False,
            )
        except InboundWebhook.DoesNotExist:
            return Response(
                {"detail": "Webhook endpoint not found or inactive."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload_bytes = request.body
        headers_dict = dict(request.headers)

        # Parse payload JSON if present
        try:
            payload_data = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
        except Exception:
            payload_data = {"raw": payload_bytes.decode("utf-8", errors="ignore")}

        # Extract event type from header or body
        event_type = (
            headers_dict.get("X-Github-Event")
            or headers_dict.get("x-github-event")
            or payload_data.get("type")
            or payload_data.get("event")
            or "webhook.event"
        )

        # Verify HMAC signature
        is_valid, err_msg = verify_hmac_signature(
            provider=webhook.provider,
            secret_token=webhook.secret_token,
            payload_bytes=payload_bytes,
            headers=headers_dict,
        )

        event_status = (
            WebhookEvent.STATUS_PROCESSED if is_valid else WebhookEvent.STATUS_FAILED
        )

        # Record webhook event log
        event_log = WebhookEvent.objects.create(
            webhook=webhook,
            organization=webhook.organization,
            event_type=event_type,
            payload=payload_data,
            headers=headers_dict,
            status=event_status,
            error_message=err_msg,
        )

        if not is_valid:
            return Response(
                {
                    "detail": "HMAC signature verification failed.",
                    "error": err_msg,
                    "event_id": str(event_log.id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": "received",
                "event_id": str(event_log.id),
                "event_type": event_type,
            },
            status=status.HTTP_200_OK,
        )

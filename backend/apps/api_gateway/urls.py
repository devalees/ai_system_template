"""
URL routing configuration for Developer API Gateway app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.api_gateway.views import (
    APIKeyViewSet,
    InboundWebhookViewSet,
    WebhookEventViewSet,
    InboundWebhookIngestView,
)

app_name = "api_gateway"

router = DefaultRouter()
router.register("keys", APIKeyViewSet, basename="key")
router.register("webhooks/configs", InboundWebhookViewSet, basename="webhook-config")
router.register("webhooks/events", WebhookEventViewSet, basename="webhook-event")

urlpatterns = [
    path("webhooks/<slug:slug>/ingest/", InboundWebhookIngestView.as_view(), name="webhook-ingest"),
    path("", include(router.urls)),
]

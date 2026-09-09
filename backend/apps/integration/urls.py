from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health_check,
    agent_handshake,
    list_handshake_logs,
    ping_hermes_gateway,
    AgentProfileViewSet,
    SpendReportViewSet,
    AgentTaskViewSet,
    list_hermes_providers,
    list_hermes_models,
    list_hermes_profiles,
)

router = DefaultRouter()
router.register(r'profiles', AgentProfileViewSet, basename='agent-profile')
router.register(r'tasks', AgentTaskViewSet, basename='agent-task')
router.register(r'spend-reports', SpendReportViewSet, basename='spend-report')

urlpatterns = [
    path('health/', health_check, name='api-health'),
    path('handshake/', agent_handshake, name='api-handshake'),
    path('handshake/logs/', list_handshake_logs, name='api-handshake-logs'),
    path('ping-hermes/', ping_hermes_gateway, name='api-ping-hermes'),
    path('hermes/providers/', list_hermes_providers, name='hermes-providers'),
    path('hermes/models/', list_hermes_models, name='hermes-models'),
    path('hermes/profiles/', list_hermes_profiles, name='hermes-profiles'),
    path('', include(router.urls)),
]
